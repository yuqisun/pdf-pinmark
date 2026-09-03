import os
import secrets
from .cache import SessionCache
from .config import Config
from .tempstore import TempStore
from .locator import highlight_rects
from . import engine


class Session:
    def __init__(self, config: Config):
        char_budget = config.cache_mb * 1024 * 1024 // 6
        self.config = config
        self.cache = SessionCache(char_budget)
        self.doc_by_id = {}
        self.id_by_path = {}
        self.hl_store = {}
        self.copy_store = {}
        self.http_port = 0
        self.tmp = TempStore(config.tmp_dir or _default_tmp())

    def get_or_parse(self, path: str):
        from . import fingerprint, parser
        rp = os.path.abspath(path)
        if rp in self.id_by_path:
            return self.id_by_path[rp], self.doc_by_id[self.id_by_path[rp]]
        size, mtime = fingerprint.quick(rp)
        doc = self.cache.get(rp, size, mtime)
        if doc is None:
            _, _, hash64 = fingerprint.of(rp)
            doc = parser.parse(rp, fingerprint=hash64)
            self.cache.put(rp, size, mtime, hash64, doc)
        if rp not in self.id_by_path:
            doc_id = secrets.token_urlsafe(16)
            self.id_by_path[rp] = doc_id
            self.doc_by_id[doc_id] = doc
        return self.id_by_path[rp], doc

    def resolve(self, doc_id: str):
        return self.doc_by_id.get(doc_id)

    def make_view_url(self, doc_id, page, context_rects, term_rects):
        hl = _encode_rects(context_rects)
        khl = _encode_rects(term_rects)
        if len(hl) + len(khl) > 1500:
            hlid = secrets.token_urlsafe(8)
            self.hl_store[hlid] = {"context": context_rects, "terms": term_rects}
            return f"http://127.0.0.1:{self.http_port}/view?doc={doc_id}&page={page}&hlid={hlid}", hlid
        url = f"http://127.0.0.1:{self.http_port}/view?doc={doc_id}&page={page}"
        if hl:
            url += f"&hl={hl}"
        if khl:
            url += f"&khl={khl}"
        return url, None

    def _make_hit(self, doc_id, doc, para, thits, score, spans, page, view_url):
        name = os.path.basename(doc.path)
        snippet = doc.orig_text[spans[0][0]:spans[0][1]][:500]
        return {
            "doc_id": doc_id, "path_display": name, "page": page,
            "offset_start": spans[0][0], "offset_end": spans[0][1],
            "snippet": snippet, "score": round(score, 2),
            "terms_hit": sorted(thits),
            "highlight_spans": [{"page": _page_1based(doc, s), "offset_start": s, "offset_end": e} for s, e in spans],
            "view_url": view_url,
            "citation": f"[《{name}》 p.{page}]({view_url})",
        }

    def search(self, scope, terms, top_k, highlight, query=""):
        import glob as _glob
        if scope["kind"] == "file":
            files = [scope["path"]]
        else:
            files = sorted(_glob.glob(scope["path"].rstrip("/\\") + "/**/*.pdf", recursive=scope.get("recursive", True)))
        weights = engine._terms_with_weights(terms, query)
        total_chars = 0
        truncated = False
        results = []
        per_file_top = []
        files_scanned = files_skipped = 0
        agg_term_hits = {}
        for f in files:
            if not f.lower().endswith(".pdf"):
                files_skipped += 1
                continue
            try:
                doc_id, doc = self.get_or_parse(f)
            except Exception:
                files_skipped += 1
                continue
            files_scanned += 1
            total_chars += len(doc.orig_text)
            if total_chars > self.config.search_limit:
                truncated = True
                break
            hits, term_hits, _ = engine.search_document(doc, weights, top_k, highlight)
            for t, c in term_hits.items():
                agg_term_hits[t] = agg_term_hits.get(t, 0) + c
            for score, para, thits in hits:
                spans = engine._highlight_spans(doc, para, thits, highlight)
                first_page = _page_1based(doc, spans[0][0]) if spans else 1
                context_rects = _rects_for(doc, [] if highlight == "term" else spans)
                term_rects = _rects_for(doc, engine._term_spans(thits))
                view_url, _ = self.make_view_url(doc_id, first_page, context_rects, term_rects)
                results.append(self._make_hit(doc_id, doc, para, thits, score, spans, first_page, view_url))
            if hits:
                per_file_top.append({"doc_id": doc_id, "path_display": os.path.basename(doc.path), "best_score": hits[0][0]})
        results.sort(key=lambda h: (-h["score"], h["page"]))
        return {
            "results": results[:top_k],
            "max_score": max((h["score"] for h in results), default=0.0),
            "term_hits": agg_term_hits,
            "files_parsed": files_scanned,
            "files_scanned": files_scanned,
            "files_skipped": files_skipped,
            "per_file_top": per_file_top,
            "truncated": truncated,
        }

    def cite(self, doc_id, quote, page_hint=None):
        doc = self.resolve(doc_id)
        if doc is None:
            return []
        import re as _re
        from .normalize import normalize_range
        from .matcher import cjk_variants
        norm, n2o = normalize_range(doc.orig_text, 0, len(doc.orig_text), doc.line_ends)
        out = []
        for v in cjk_variants(quote.lower()):  # 简繁变体都尝试，简体引文可命中繁体原文
            chars = _re.sub(r"\s+", "", v)
            if not chars:
                continue
            # 空白不敏感：每字符间允许任意空白（跨行引文与原文空格差异均可容忍）
            pat = r"\s*".join(_re.escape(c) for c in chars)
            start = 0
            while True:
                m = _re.search(pat, norm[start:])
                if m is None:
                    break
                i = start + m.start()
                o0 = n2o[i]
                o1 = n2o[i + m.end() - m.start() - 1] + 1
                pg = _page_1based(doc, o0)
                if page_hint is None or pg == page_hint:
                    rects = highlight_rects(doc, o0, o1)
                    url, _ = self.make_view_url(doc_id, pg, {}, rects)
                    name = os.path.basename(doc.path)
                    out.append({"page": pg, "offset_start": o0, "offset_end": o1,
                                "snippet": doc.orig_text[o0:o1], "view_url": url,
                                "citation": f"[《{name}》 p.{pg}]({url})"})
                start = i + 1
        # 去重（同一位置可能被多个变体重复匹配）
        deduped, seen = [], set()
        for m in out:
            key = (m["page"], m["offset_start"], m["offset_end"])
            if key not in seen:
                seen.add(key)
                deduped.append(m)
        return deduped

    def get_more(self, doc_id, page, offset_start, offset_end, before=600, after=600):
        doc = self.resolve(doc_id)
        if doc is None:
            return {"text": ""}
        a = max(0, offset_start - before)
        b = min(len(doc.orig_text), offset_end + after)
        name = os.path.basename(doc.path)
        rects = highlight_rects(doc, offset_start, offset_end)
        view_url, _ = self.make_view_url(doc_id, page, {}, rects)
        return {"text": doc.orig_text[a:b], "page": page, "start": a, "end": b,
                "view_url": view_url, "citation": f"[《{name}》 p.{page}]({view_url})"}

    def read_pages(self, doc_id, from_page, to_page, max_chars=None):
        doc = self.resolve(doc_id)
        if doc is None:
            return []
        out = []
        for p in doc.pages:
            if from_page - 1 <= p.page_no <= to_page - 1:
                text = "\n".join(l.text for l in p.lines)
                if max_chars:
                    text = text[:max_chars]
                page_url, _ = self.make_view_url(doc_id, p.page_no + 1, {}, {})
                # 注意：page_url 只是"跳到该页"的导航链接，无高亮，不作为引用出处
                out.append({"page": p.page_no + 1, "text": text, "page_url": page_url})
        return out

    def list_documents(self, path, recursive=True):
        import glob as _glob
        pattern = path.rstrip("/\\") + "/**/*.pdf" if recursive else path + "/*.pdf"
        return [{"path_display": os.path.basename(f), "path": f, "pages": None, "parsed": False}
                for f in sorted(_glob.glob(pattern, recursive=recursive))]

    def download_annotated(self, doc_id, spans):
        import fitz
        doc = self.resolve(doc_id)
        if doc is None:
            return {"error": "unknown doc_id"}
        src = fitz.open(doc.path)
        for span in spans:
            rects = highlight_rects(doc, span["offset_start"], span["offset_end"])
            for pno, rs in rects.items():
                for r in rs:
                    src[pno].add_highlight_annot(fitz.Rect(r))
        data = src.tobytes()
        src.close()
        path, copy_id = self.tmp.add(data, ".pdf")
        self.copy_store[copy_id] = path
        return {"download_url": f"http://127.0.0.1:{self.http_port}/download/{copy_id}",
                "temp_path": path, "retention_note": "24h 后或进程退出时清理"}


def _page_1based(doc, offset):
    for p in doc.pages:
        if p.global_start <= offset < p.global_start + p.char_count + len(p.lines):
            return p.page_no + 1
    return 1


def _encode_rects(rects):
    return ";".join(f"{p+1}:{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}"
                    for p, rs in rects.items() for (x0, y0, x1, y1) in rs)


def _rects_for(doc, spans):
    rects = {}
    for s0, s1 in spans:
        for pg, rs in highlight_rects(doc, s0, s1).items():
            rects.setdefault(pg, []).extend(rs)
    return rects


def _default_tmp():
    import tempfile
    return os.path.join(tempfile.gettempdir(), "pdf-nl-search-mcp")

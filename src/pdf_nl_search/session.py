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

    def make_view_url(self, doc_id, page, rects):
        hl = ";".join(f"{p+1}:{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}"
                      for p, rs in rects.items() for (x0, y0, x1, y1) in rs)
        if len(hl) > 1500:
            hlid = secrets.token_urlsafe(8)
            self.hl_store[hlid] = rects
            return f"http://127.0.0.1:{self.http_port}/view?doc={doc_id}&page={page}&hlid={hlid}", hlid
        return f"http://127.0.0.1:{self.http_port}/view?doc={doc_id}&page={page}&hl={hl}", None

    def _make_hit(self, doc_id, doc, para, thits, score, spans, page, view_url):
        name = os.path.basename(doc.path)
        snippet = doc.orig_text[spans[0][0]:spans[0][1]][:500]
        return {
            "doc_id": doc_id, "path_display": name, "page": page,
            "offset_start": para.start, "offset_end": para.end,
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
                rects = {}
                for s0, s1 in spans:
                    for pg, rs in highlight_rects(doc, s0, s1).items():
                        rects.setdefault(pg, []).extend(rs)
                view_url, _ = self.make_view_url(doc_id, first_page, rects)
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


def _page_1based(doc, offset):
    for p in doc.pages:
        if p.global_start <= offset < p.global_start + p.char_count + len(p.lines):
            return p.page_no + 1
    return 1


def _default_tmp():
    import tempfile
    return os.path.join(tempfile.gettempdir(), "pdf-nl-search-mcp")

from .matcher import is_cjk_term, find_terms, fallback_terms
from .normalize import normalize_range
from .scorer import compute_idf, score_paragraph, ScoreArgs
from .models import ParsedDocument

SENTENCE_END = "。！？；.!?;"


def _terms_with_weights(terms, query):
    if terms:
        return {t: 1.0 for t in terms}
    return {t: 1.0 for t in fallback_terms(query)}


def _match_paragraph(doc, para, weights):
    norm, n2o = normalize_range(doc.orig_text, para.start, para.end, doc.line_ends)
    hits = {}
    for term in weights:
        cjk = is_cjk_term(term)
        spans = find_terms(norm, term.lower() if not cjk else term, cjk)
        if spans:
            hits[term] = [(n2o[s], n2o[e - 1] + 1) for s, e in spans]  # 转回原文偏移
    return hits


def _sentence_span(doc, start, end):
    text = doc.orig_text
    a = start
    while a > 0 and text[a - 1] not in SENTENCE_END and text[a - 1] != "\n":
        a -= 1
    b = end
    while b < len(text) and text[b] not in SENTENCE_END and text[b] != "\n":
        b += 1
    if b < len(text) and text[b] in SENTENCE_END:
        b += 1
    return a, b


def _highlight_spans(doc, para, hits, mode):
    if mode == "paragraph":
        return [(para.start, para.end)]
    if mode == "term":
        spans = []
        for lst in hits.values():
            spans.extend(lst)
        return spans
    # sentence（默认）：每个命中扩到句边界
    windows = [_sentence_span(doc, s, e) for lst in hits.values() for s, e in lst]
    return windows


def search_document(doc, weights, top_k, highlight):
    N = len(doc.paragraphs)
    per_para = {}
    df = {}
    for para in doc.paragraphs:
        hits = _match_paragraph(doc, para, weights)
        if hits:
            per_para[id(para)] = (para, hits)
            for t in hits:
                df[t] = df.get(t, 0) + 1
    idf = compute_idf(df, N)
    args = ScoreArgs(weights=weights, idf=idf)
    scored = []
    for para, hits in per_para.values():
        s = score_paragraph(args, hits)
        scored.append((s, para, hits))
    scored.sort(key=lambda x: (-x[0], x[1].page_no, x[1].start))
    term_hits = {t: df.get(t, 0) for t in weights}
    return scored[:top_k], term_hits, max((s for s, _, _ in scored), default=0.0)

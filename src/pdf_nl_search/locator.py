import bisect
from .models import ParsedDocument, Rect


def highlight_rects(doc: ParsedDocument, start: int, end: int, pad: float = 1.0) -> dict[int, list[Rect]]:
    """返回 {page_no(0-based): [rect,...]}。行内重叠词的矩形取并集，不跨行合并。"""
    lines = [l for p in doc.pages for l in p.lines]
    starts = [l.global_start for l in lines]
    idx = bisect.bisect_right(starts, start) - 1
    result: dict[int, list[Rect]] = {}
    while idx < len(lines) and lines[idx].global_start < end:
        line = lines[idx]
        page = _page_of(doc, line)
        rects = []
        for (wrect, wstart, wend) in line.words:
            if wend > start and wstart < end:  # 词区间与 [start,end) 重叠
                rects.append(wrect)
        if rects:
            result.setdefault(page.page_no, []).append(_union(rects, pad))
        idx += 1
    return result


def _page_of(doc, line):
    for p in doc.pages:
        if p.global_start <= line.global_start < p.global_start + p.char_count + len(p.lines):
            return p
    return doc.pages[-1]


def _union(rects, pad):
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)

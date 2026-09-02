import bisect
import fitz
from .models import ParsedDocument, Rect


def highlight_rects(doc: ParsedDocument, start: int, end: int, pad: float = 1.0) -> dict[int, list[Rect]]:
    """返回 {page_no(0-based): [rect,...]}，按行合并不跨行。"""
    lines = [l for p in doc.pages for l in p.lines]
    starts = [l.global_start for l in lines]
    idx = bisect.bisect_right(starts, start) - 1
    result: dict[int, list[Rect]] = {}
    while idx < len(lines) and lines[idx].global_start < end:
        line = lines[idx]
        page = _page_of(doc, line)
        seg_start = max(start, line.global_start)
        seg_end = min(end, line.global_start + len(line.text))
        if seg_end > seg_start:
            boxes = _page_char_boxes(doc, page.page_no)
            local = _local_range(page, line, seg_start, seg_end)
            rect = _merge_boxes(boxes, local, pad)
            if rect is not None:
                result.setdefault(page.page_no, []).append(rect)
        idx += 1
    return result


def _page_of(doc, line):
    for p in doc.pages:
        if p.global_start <= line.global_start < p.global_start + p.char_count + len(p.lines):
            return p
    return doc.pages[-1]


def _local_range(page, line, seg_start, seg_end):
    base = seg_start - page.global_start - line.page_line_index
    return (base, base + (seg_end - seg_start))


def _page_char_boxes(doc, page_no):
    d = fitz.open(doc.path)
    try:
        p = d[page_no]
        boxes = []
        for block in p.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for ln in block["lines"]:
                for span in ln["spans"]:
                    for ch in span["chars"]:
                        boxes.append(fitz.Rect(ch["bbox"]))
        return boxes
    finally:
        d.close()


def _merge_boxes(boxes, local, pad):
    a, b = local
    if a >= b or b > len(boxes):
        return None
    r = boxes[a]
    for i in range(a + 1, b):
        r |= boxes[i]
    r = fitz.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
    return (r.x0, r.y0, r.x1, r.y1)

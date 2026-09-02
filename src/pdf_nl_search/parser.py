import fitz
from .models import Line, Page, Paragraph, ParsedDocument


def parse(path: str, fingerprint: str = "") -> ParsedDocument:
    d = fitz.open(path)
    pages: list[Page] = []
    cursor = 0
    all_lines: list[Line] = []
    try:
        for pno in range(d.page_count):
            page = d[pno]
            lines: list[Line] = []
            page_global_start = cursor
            data = page.get_text("dict", sort=True)
            for block in data["blocks"]:
                if block.get("type") != 0:
                    continue
                for ln in block["lines"]:
                    text = "".join(s["text"] for s in ln["spans"])
                    if not text:
                        continue
                    line = Line(text=text, rect=tuple(fitz.Rect(ln["bbox"])),
                                global_start=cursor, page_line_index=len(lines))
                    lines.append(line)
                    all_lines.append(line)
                    cursor += len(text)
                    cursor += 1  # 行尾 \n
            pages.append(Page(page_no=pno, rect=tuple(page.rect), global_start=page_global_start,
                              char_count=sum(len(l.text) for l in lines), lines=lines))
    finally:
        d.close()
    orig_text = "\n".join(l.text for l in all_lines) + "\n"
    line_ends = {l.global_start + len(l.text) - 1 for l in all_lines}
    paragraphs = _segment(pages)
    return ParsedDocument(path=path, fingerprint=fingerprint, orig_text=orig_text,
                          pages=pages, paragraphs=paragraphs, line_ends=line_ends)


def _segment(pages) -> list[Paragraph]:
    """按行几何切段：垂直间距过大或水平明显错位视为新段落，否则同段。"""
    paragraphs = []
    for page in pages:
        lines = page.lines
        if not lines:
            continue
        para_start = lines[0].global_start
        prev = lines[0]
        for line in lines[1:]:
            gap = line.rect[1] - prev.rect[3]      # 新行顶 - 前行底
            x_shift = abs(line.rect[0] - prev.rect[0])
            line_h = (prev.rect[3] - prev.rect[1]) or 10.0
            if gap > 1.5 * line_h or x_shift > 5.0:
                paragraphs.append(Paragraph(page_no=page.page_no, start=para_start,
                                            end=prev.global_start + len(prev.text)))
                para_start = line.global_start
            prev = line
        paragraphs.append(Paragraph(page_no=page.page_no, start=para_start,
                                    end=prev.global_start + len(prev.text)))
    return paragraphs

import fitz
from itertools import groupby
from .models import Line, Page, Paragraph, ParsedDocument


def _lines_from_words(words):
    """从 words 模式重建行：按 (block_no, line_no) 分组，词间按 x 间隙补空格，记录每词 rect+相对偏移。

    words 模式比 dict/rawdict 快约 1000 倍（不做嵌入字体的逐字符解码）。
    间隙 >1.0pt 视为真实空格（Latin 词间）；CJK 相邻字符间隙≈0，故不加空格、文本连续。
    """
    out = []
    for (_blk, _ln), grp in groupby(words, key=lambda w: (w[5], w[6])):
        ws = sorted(grp, key=lambda w: w[0])  # 按 x0 排序
        if not ws:
            continue
        text_parts = []
        rel = 0
        word_spans = []
        prev = None
        for w in ws:
            word_text = w[4]
            word_rect = (w[0], w[1], w[2], w[3])
            if prev is not None and (w[0] - prev[2]) > 1.0:
                text_parts.append(" ")
                rel += 1
            word_spans.append((word_rect, rel, rel + len(word_text)))
            text_parts.append(word_text)
            rel += len(word_text)
            prev = w
        text = "".join(text_parts)
        rect = (min(w[0] for w in ws), min(w[1] for w in ws),
                max(w[2] for w in ws), max(w[3] for w in ws))
        out.append((text, rect, word_spans))
    return out


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
            for text, rect, word_spans in _lines_from_words(page.get_text("words")):
                line = Line(text=text, rect=rect, global_start=cursor, page_line_index=len(lines))
                for (wrect, rel_start, rel_end) in word_spans:
                    line.words.append((wrect, cursor + rel_start, cursor + rel_end))
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

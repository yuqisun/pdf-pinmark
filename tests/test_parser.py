from pdf_nl_search.parser import parse


def test_parse_builds_lines_and_offsets(sample_pdf):
    doc = parse(str(sample_pdf))
    assert len(doc.pages) == 2
    # 第一页两行，第二页两行（断词跨行）
    assert len(doc.pages[0].lines) == 2
    assert doc.pages[1].lines[0].text.startswith("This is the transfor-")
    # 全局偏移：第二行起点 = 第一行起点 + 长度 + 1（行间 \n）
    l0 = doc.pages[0].lines[0]
    l1 = doc.pages[0].lines[1]
    assert l1.global_start == l0.global_start + len(l0.text) + 1
    # line_ends 记录每行末字符偏移
    assert l0.global_start + len(l0.text) - 1 in doc.line_ends


def test_paragraph_spans_lines_for_cross_line_match(sample_pdf):
    from pdf_nl_search.normalize import normalize_range
    doc = parse(str(sample_pdf))
    assert len(doc.paragraphs) >= 1
    # 第二页两行（断词跨行）应属同一段落，归一化后 "transformer" 可命中
    para = doc.paragraphs[-1]
    norm, _ = normalize_range(doc.orig_text, para.start, para.end, doc.line_ends)
    assert "transformer" in norm

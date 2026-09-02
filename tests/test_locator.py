from pdf_nl_search.parser import parse
from pdf_nl_search.locator import highlight_rects
from tests.conftest import make_pdf


def test_rects_within_line_band(tmp_path):
    p = make_pdf(tmp_path / "t.pdf", [["营业收入 9,328.5 亿元"]])
    doc = parse(str(p))
    line = doc.pages[0].lines[0]
    rects = highlight_rects(doc, line.global_start, line.global_start + 4)  # "营业"
    assert len(rects) == 1
    (r,) = rects[0]
    x0, y0, x1, y1 = r
    assert y0 >= 50 and y1 <= 120
    assert x0 < x1
    assert x0 >= 60


def test_cross_page_span_gives_two_page_rects(tmp_path):
    p = make_pdf(tmp_path / "t2.pdf", [["one line"], ["another line"]])
    doc = parse(str(p))
    l0 = doc.pages[0].lines[0]
    l1 = doc.pages[1].lines[0]
    rects = highlight_rects(doc, l0.global_start, l1.global_start + 3)
    assert set(rects.keys()) == {0, 1}

from pdf_nl_search.session import Session
from pdf_nl_search.config import Config
from tests.conftest import make_pdf


def _session(tmp_path):
    return Session(Config(cache_mb=1024, search_limit=10_000, log_level="info", tmp_dir=str(tmp_path / "tmp")))


def test_search_hits_sentence(tmp_path):
    p = make_pdf(tmp_path / "r.pdf", [["2025 年，比亚迪实现营业收入约 9,328.5 亿元。"]])
    s = _session(tmp_path)
    res = s.search({"kind": "file", "path": str(p)}, ["比亚迪", "营业收入", "2025"], top_k=3, highlight="sentence")
    assert len(res["results"]) >= 1
    hit = res["results"][0]
    assert hit["page"] == 1
    assert "营业收入" in hit["snippet"]
    assert hit["view_url"].startswith("http://127.0.0.1:")
    assert hit["citation"].startswith("[《")
    assert res["max_score"] > 0


def test_search_empty_returns_term_hits(tmp_path):
    p = make_pdf(tmp_path / "r2.pdf", [["hello world"]])
    s = _session(tmp_path)
    res = s.search({"kind": "file", "path": str(p)}, ["比亚迪"], top_k=3, highlight="sentence")
    assert res["results"] == []
    assert res["term_hits"]["比亚迪"] == 0


def test_cite_and_get_more(tmp_path):
    p = make_pdf(tmp_path / "c.pdf", [["营业收入 9,328.5 亿元"], ["净利润 405.4 亿元"]])
    s = _session(tmp_path)
    doc_id, _ = s.get_or_parse(str(p))
    matches = s.cite(doc_id, "营业收入 9,328.5 亿元")
    assert len(matches) >= 1
    assert matches[0]["page"] == 1
    assert matches[0]["view_url"]
    more = s.get_more(doc_id, 1, matches[0]["offset_start"], matches[0]["offset_end"])
    assert "营业收入" in more["text"]


def test_cite_quote_not_found(tmp_path):
    p = make_pdf(tmp_path / "c2.pdf", [["hello"]])
    s = _session(tmp_path)
    doc_id, _ = s.get_or_parse(str(p))
    assert s.cite(doc_id, "不存在的引文") == []


def test_cite_whitespace_insensitive(tmp_path):
    # 引文不含空格也能命中含空格的原文（跨行引文场景）
    p = make_pdf(tmp_path / "c3.pdf", [["营业收入 9,328.5 亿元"]])
    s = _session(tmp_path)
    doc_id, _ = s.get_or_parse(str(p))
    assert len(s.cite(doc_id, "营业收入9,328.5亿元")) >= 1

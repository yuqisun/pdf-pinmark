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

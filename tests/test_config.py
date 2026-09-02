import os
from pdf_nl_search import config


def test_defaults(monkeypatch):
    for k in ["PDFNL_CACHE_MB", "PDFNL_SEARCH_LIMIT", "PDFNL_LOG_LEVEL", "PDFNL_TMP_DIR"]:
        monkeypatch.delenv(k, raising=False)
    c = config.load()
    assert c.cache_mb == 1024
    assert c.search_limit == 20_000_000
    assert c.log_level == "info"
    assert c.tmp_dir is None


def test_override(monkeypatch):
    monkeypatch.setenv("PDFNL_CACHE_MB", "2048")
    monkeypatch.setenv("PDFNL_LOG_LEVEL", "debug")
    c = config.load()
    assert c.cache_mb == 2048
    assert c.log_level == "debug"


def test_bad_int_falls_back(monkeypatch):
    monkeypatch.setenv("PDFNL_CACHE_MB", "abc")
    assert config.load().cache_mb == 1024

from pdf_nl_search.tools import make_tools
from pdf_nl_search.session import Session
from pdf_nl_search.config import Config
from tests.conftest import make_pdf


def test_search_tool_returns_envelope(tmp_path):
    p = make_pdf(tmp_path / "t.pdf", [["2025 年，比亚迪营业收入 9,328.5 亿元"]])
    s = Session(Config(1024, 10000, "info", str(tmp_path / "tmp")))
    tools = make_tools(s)
    out = tools["search"](scope={"kind": "file", "path": str(p)},
                          terms=["比亚迪", "营业收入"], top_k=3, highlight="sentence", query="")
    assert "results" in out and "term_hits" in out


def test_server_imports_and_registers_tools():
    import pdf_nl_search.server as server
    assert server.mcp is not None
    for name in ("search", "cite", "get_more", "read_pages", "list_documents", "download_annotated"):
        assert callable(getattr(server, name, None))

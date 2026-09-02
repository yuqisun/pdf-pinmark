import logging
import sys
import threading
from mcp.server.mcpserver import MCPServer
from .config import load
from .session import Session
from .tools import make_tools

mcp = MCPServer("pdf-nl-search")
_session = None
_tools = {}


def _ensure():
    global _session, _tools
    if _session is None:
        _session = Session(load())
        _tools = make_tools(_session)
    return _session, _tools


@mcp.tool()
def search(scope: dict, terms: list = None, top_k: int = 10, highlight: str = "sentence", query: str = "") -> dict:
    """按词表对 scope 内 PDF 做段落级检索。terms 应为语料语言的多语同义改写词表。
    对数值/事实类问题，作答前先用 get_more/read_pages 核对口径、单位、年份再引用。"""
    _, tools = _ensure()
    return tools["search"](scope, terms or [], top_k, highlight, query)


@mcp.tool()
def cite(doc_id: str, quote: str, page_hint: int = None) -> dict:
    """把宿主确认的一小段原文重新定位，返回可高亮该处的链接。"""
    _, tools = _ensure()
    return tools["cite"](doc_id, quote, page_hint)


@mcp.tool()
def get_more(doc_id: str, page: int, offset_start: int, offset_end: int,
             context_chars_before: int = 600, context_chars_after: int = 600) -> dict:
    """取命中点周边更大连续文本。"""
    _, tools = _ensure()
    return tools["get_more"](doc_id, page, offset_start, offset_end,
                             context_chars_before, context_chars_after)


@mcp.tool()
def read_pages(doc_id: str, from_page: int, to_page: int, max_chars: int = None) -> dict:
    """通读指定页区间原文。"""
    _, tools = _ensure()
    return tools["read_pages"](doc_id, from_page, to_page, max_chars)


@mcp.tool()
def list_documents(path: str, recursive: bool = True) -> dict:
    """列出目录内可检索的 PDF（不解析）。"""
    _, tools = _ensure()
    return tools["list_documents"](path, recursive)


@mcp.tool()
def download_annotated(doc_id: str, spans: list) -> dict:
    """按需生成带批注副本并返回下载 URL。"""
    _, tools = _ensure()
    return tools["download_annotated"](doc_id, spans)


def main():
    logging.basicConfig(level=getattr(logging, load().log_level.upper(), logging.INFO),
                        stream=sys.stderr)  # 日志只去 stderr，stdout 仅走 JSON-RPC
    session, _ = _ensure()
    from .http import start_server
    srv, _ = start_server(session)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    mcp.run()


if __name__ == "__main__":
    main()

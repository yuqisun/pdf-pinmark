import asyncio
import os
import sys

import pytest

from tests.conftest import make_pdf

# 沙箱禁止子进程管道捕获（EPERM），本 e2e 需在用户本机运行：
#   PDFNL_SKIP_E2E=1 pytest tests/test_e2e.py   （沙箱内跳过）
#   pytest tests/test_e2e.py -v                （本机运行）
pytestmark = pytest.mark.skipif(
    os.environ.get("PDFNL_SKIP_E2E") == "1",
    reason="sandbox blocks subprocess stdio pipes",
)


def test_sdk_client_roundtrip(tmp_path):
    p = make_pdf(tmp_path / "e.pdf", [["2025 年，比亚迪营业收入 9,328.5 亿元"]])
    env = dict(os.environ, PDFNL_CACHE_MB="1024")

    async def run():
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(
            command=sys.executable, args=["-m", "pdf_nl_search"], env=env
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                assert {
                    "search",
                    "cite",
                    "get_more",
                    "read_pages",
                    "list_documents",
                    "download_annotated",
                } <= names
                result = await session.call_tool(
                    "search",
                    {
                        "scope": {"kind": "file", "path": str(p)},
                        "terms": ["比亚迪", "营业收入"],
                        "top_k": 3,
                        "highlight": "sentence",
                    },
                )
                assert result is not None

    asyncio.run(run())

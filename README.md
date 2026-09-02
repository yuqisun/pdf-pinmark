# pdf-nl-search-mcp

对**文字版 PDF** 做自然语言检索的本地 MCP server：让 LLM 宿主（Claude Code / opencode / VSCode）按自然语言在 PDF 里检索，返回**可点击、能在浏览器精确高亮原文出处**的链接。

- 单机单用户、只读源文件、无索引、无向量、完全离线。
- 支持单个文件或整个目录。
- 高亮由 pdf.js 自绘层实现，任意现代浏览器一致可见。

## 安装（只需装 uv）

```powershell
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
git clone <repo> && cd pdf-pinmark
uv sync
```

## 下载 pdf.js 静态资源（离线查看需要）

```bash
python scripts/fetch_pdfjs.py
```

会把 `pdf.mjs` / `pdf.worker.mjs` 下载到 `src/pdf_nl_search/assets/pdfjs/`（Apache-2.0，随包分发）。

## 配置 MCP 客户端

Claude Code（`.mcp.json`）、opencode（`opencode.json` 的 mcp 段）、VSCode（Copilot/Cline/Continue 的 `.mcp.json`）三端同结构：

```json
{
  "mcpServers": {
    "pdf-nl-search": {
      "command": "uv",
      "args": ["run", "pdf-nl-search-mcp"],
      "env": { "PDFNL_CACHE_MB": "1024" }
    }
  }
}
```

Windows 上 `uv` 若不在 PATH，可写绝对路径（如 `C:\\Users\\<you>\\.local\\bin\\uv.exe`）。

## 环境变量

| 变量 | 默认 | 用途 |
|---|---|---|
| `PDFNL_CACHE_MB` | 1024 | 会话解析缓存内存预算（LRU 上限） |
| `PDFNL_SEARCH_LIMIT` | 20000000 | 单次 search 解析上限（字符数，目录超限即 truncated） |
| `PDFNL_LOG_LEVEL` | info | 日志级别（写 stderr） |
| `PDFNL_TMP_DIR` | 系统临时目录 | 批注副本存放目录 |

## 使用

配置好后，在 Claude Code / opencode 里直接问：

> 根据 D:\reports\BYD_2025_annual.pdf，告诉我 BYD 2025 年营收是多少。

宿主会调 `search` 检索、返回带 `view_url` 链接的结果；点击链接即在浏览器打开对应页并高亮原文。

## 工具

- `search(scope, terms, top_k, highlight)` —— 段落级检索（terms 由宿主改写为多语同义词表）
- `cite(doc_id, quote, page_hint?)` —— 把宿主确认的原文片段重新定位并给出高亮链接
- `get_more(doc_id, page, offset_start, offset_end, ...)` —— 取命中点更大上下文
- `read_pages(doc_id, from_page, to_page)` —— 通读页区间
- `list_documents(path, recursive)` —— 列目录内 PDF
- `download_annotated(doc_id, spans)` —— 生成带批注副本并下载

## 性能说明

- 首次搜索一个文件时需**按需解析**（无预建索引，这是设计选择）：小/中 PDF 秒级；**带嵌入 CJK 字体的大 PDF（如 33MB 年报）首次解析较慢**（PyMuPDF 逐字符提取坐标是瓶颈），解析结果在会话内存缓存，后续搜索很快。
- 已记录的未来优化：改用 `get_text("words")` 模式快速重建行（经验证与 `text` 模式逐行一致），配合词级高亮可把大 PDF 解析提速约 1000 倍。

## 测试

```bash
# 单元 + 集成（无需网络/浏览器）
uv run pytest tests/ --ignore=tests/test_e2e.py

# 端到端（需要能 spawn 子进程的本机环境）
uv run pytest tests/test_e2e.py -v
```

## 设计

详见 `docs/superpowers/specs/2026-09-02-pdf-nl-search-mcp-design.md` 与 `docs/superpowers/plans/2026-09-02-pdf-nl-search-mcp.md`。

# pdf-nl-search-mcp

A local MCP server for **natural-language search over text-layer PDFs**. It lets LLM hosts (Claude Code / opencode / VSCode) search inside PDFs in natural language and return **clickable links that open the exact source page with the original text highlighted** in your browser.

- Single-machine, single-user, read-only on source files; no index, no vector DB, fully offline.
- Works on a single file or an entire directory.
- Highlighting is drawn by a pdf.js overlay layer, so it looks the same in any modern browser.

## Install (only uv required)

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

## Download the pdf.js assets (required for offline viewing)

```bash
python scripts/fetch_pdfjs.py
```

This downloads `pdf.mjs` / `pdf.worker.mjs` into `src/pdf_nl_search/assets/pdfjs/` (Apache-2.0, bundled with the package).

## Configure the MCP client

First locate the executable entry point (either works; below we use the console script; replace `<project-path>` with your clone path, e.g. `D:\work\pdf-pinmark`):

- Console script: `<project-path>\.venv\Scripts\pdf-nl-search-mcp.exe` (Windows)
- venv python: `<project-path>\.venv\Scripts\python.exe` with args `-m pdf_nl_search`

> Using an absolute path (instead of `uv run`) is most robust: `uv run` depends on the working directory and PATH at launch time, while an absolute path always resolves.

### Claude Code

Project scope: put a `.mcp.json` in the directory where you run `claude`:

```json
{
  "mcpServers": {
    "pdf-nl-search": {
      "command": "D:\\work\\pdf-pinmark\\.venv\\Scripts\\pdf-nl-search-mcp.exe",
      "env": { "PDFNL_CACHE_MB": "1024" }
    }
  }
}
```

User scope (available in any directory):

```powershell
claude mcp add pdf-nl-search "D:\work\pdf-pinmark\.venv\Scripts\pdf-nl-search-mcp.exe"
```

If that CLI version is picky about arguments (e.g. `unknown option` / `missing argument`), fall back to `.mcp.json`, or edit the `mcpServers` field of `~/.claude.json` directly.

### opencode

Project-level `opencode.json` (or global `~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "pdf-nl-search": {
      "type": "local",
      "command": ["D:\\work\\pdf-pinmark\\.venv\\Scripts\\pdf-nl-search-mcp.exe"],
      "environment": { "PDFNL_CACHE_MB": "1024" },
      "enabled": true
    }
  }
}
```

### VSCode Copilot

Workspace-level `.vscode/mcp.json`:

```json
{
  "servers": {
    "pdf-nl-search": {
      "type": "stdio",
      "command": "D:\\work\\pdf-pinmark\\.venv\\Scripts\\pdf-nl-search-mcp.exe",
      "env": { "PDFNL_CACHE_MB": "1024" }
    }
  }
}
```

> Field names vary slightly by client version (`mcpServers` vs `servers`, `env` vs `environment`). If a client doesn't pick it up, check its current docs — the essentials are: `command` points to the console script's absolute path, and transport is stdio.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PDFNL_CACHE_MB` | 1024 | Session parse-cache memory budget (LRU cap) |
| `PDFNL_SEARCH_LIMIT` | 20000000 | Per-`search` parse cap in characters (directory searches set `truncated` when exceeded) |
| `PDFNL_LOG_LEVEL` | info | Log level (written to stderr) |
| `PDFNL_TMP_DIR` | system temp | Directory for generated annotated copies |

## Usage

After configuration, ask Claude Code / opencode directly, e.g.:

> Based on D:\reports\BYD_2025_annual.pdf, what was BYD's 2025 revenue?

The host calls `search` and returns results carrying `view_url` links; click one to open the matching page in your browser with the source highlighted.

## Tools

- `search(scope, terms, top_k, highlight)` — paragraph-level retrieval (terms are multilingual synonyms rewritten by the host)
- `cite(doc_id, quote, page_hint?)` — re-locate a confirmed source snippet and return a highlighted link
- `get_more(doc_id, page, offset_start, offset_end, ...)` — fetch wider context around a hit
- `read_pages(doc_id, from_page, to_page)` — read a page range
- `list_documents(path, recursive)` — list PDFs in a directory
- `download_annotated(doc_id, spans)` — generate and download an annotated copy

## Performance notes

- Each file is parsed **on demand** on first search (no pre-built index — a design choice). Parsing rebuilds lines via `get_text("words")` mode (no per-character decoding), so a 33 MB / 369-page annual report parses in about **1 second**; results are cached in session memory, so later searches are faster (~0.3 s).
- **Simplified/Traditional Chinese**: OpenCC is built in, so simplified queries/quotes hit traditional PDFs and vice versa; `cite` is also tolerant of whitespace differences across line breaks.

## Known limitations

- **Weak recall for key-value numbers inside tables**: if a key number is a table cell (e.g. in a performance-overview table, "460 萬輛" and its label "快報銷量" live in two separate cells), paragraph-level retrieval struggles to connect the number to its label and may miss it. A "page-context boost" mitigates dense tables, but sparse key-value tables need future "table-aware merging" for a real fix. Workarounds: search by "number + unit" or the table heading (e.g. 「業績概覽」), or browse to the page directly.

## Tests

```bash
# Unit + integration (no network / browser required)
uv run pytest tests/ --ignore=tests/test_e2e.py

# End-to-end (requires an environment that can spawn subprocesses)
uv run pytest tests/test_e2e.py -v
```

## Design

See `docs/superpowers/specs/2026-09-02-pdf-nl-search-mcp-design.md` and `docs/superpowers/plans/2026-09-02-pdf-nl-search-mcp.md`.

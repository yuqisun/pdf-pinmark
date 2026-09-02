# PDF 自然语言检索 MCP 设计文档

- 日期：2026-09-02
- 状态：已获用户逐点确认，待用户最终审阅
- 工作目录：`D:\work\pdf-pinmark`（全新项目）

## 1. 目标与背景

构建一个本地 MCP（Model Context Protocol）server，让 LLM 宿主（Claude Code、opencode、VSCode 等）能对**用户本机的文字版 PDF 语料**做自然语言检索，并让用户在浏览器中**看到命中原文的位置与高亮**。

需求清单（用户原话归纳）：
1. 搜索文字版 PDF（单个文件或目录）。
2. 支持自然语言语义搜索（区别于普通关键词搜索）。
3. 结果携带原文出处。
4. 结果附带链接，点击后在浏览器跳转到对应页。
5. 用户能看到原文出处被高亮。
6. 支持单文件与目录两种范围。
7. 可被 VSCode / Claude Code / opencode 等 MCP 客户端使用。

### 关键范围边界

- 语料为**有文字层的 PDF**，不做 OCR，不依赖多模态模型。
- 语料语言：**中英混合**。
- 个人本地使用：单机、单用户、只读源文件。
- 不预先构建任何索引，不引入 embedding/向量检索（见决策 D3）。

## 2. 已确认决策汇总

| 编号 | 主题 | 决策 |
|---|---|---|
| D1 | 实现路线 | 全新自研，复用成熟底层库（PyMuPDF 等） |
| D2 | 文本层形态 | 不生成 txt；解析结果**仅存会话内存**（LRU），不落盘 |
| D3 | 检索机制 | 检索循环：宿主 LLM 改写词表 → 按需抽取 → 段落级归一化匹配打分；schema 预留向量升级位 |
| D4 | 定位/高亮 | 原始字符流 ↔ 归一化流双向映射；字符级矩形按行合并；高亮范围 `term/sentence/paragraph` 可选，默认 `sentence`；严格归一化匹配（无拼写容错） |
| D5 | 结果链接 | 内置本地 HTTP 服务 + pdf.js 查看页，HTML 层自绘高亮；原 PDF 只读伺服；默认不生成副本 |
| D6 | 生命周期 | 唯一落盘物 = 用户主动下载的批注副本，系统临时目录 + 三层清理（进程退出/TTL 24h/数量上限）；txt 与磁盘缓存永不产生 |
| D7 | 实现栈 | Python 3.10+；mcp SDK（Python）；PyMuPDF；stdlib `http.server`；pdf.js 静态资源随包分发 |

## 3. 总体架构

```
┌─ MCP 客户端（Claude Code / opencode / VSCode 扩展）───────────────┐
│   宿主 LLM：理解自然语言、改写词表、精读片段、综合答案与引用          │
└───────────────┬──────────────────────────────────────────────────┘
                │ stdio (JSON-RPC / MCP)
┌───────────────▼──────────────────────────────────────────────────┐
│  pdf-nl-search-mcp（Python 进程，一个进程内两套服务）                │
│                                                                    │
│  ┌─ MCP 工具层 ──────────────────────────────────────────────┐   │
│  │ search / cite / get_more / read_pages / list_documents    │   │
│  │ download_annotated                                        │   │
│  └──────────────┬────────────────────────────────────────────┘   │
│                 ▼                                                  │
│  ┌─ 会话解析缓存（内存 LRU）──────────────────────────────────────┐  │
│  │ ParsedDocument{ file_hash, path, pages[] }                   │  │
│  │  page → lines[] → Line{ text, rect, char 明细惰性 }          │  │
│  │  原始字符流常驻；归一化流/map 按段惰性                        │  │
│  └──────┬────────────────────────────────────────────────────────┘  │
│         │ 按需惰性解析（首次搜到才解析该文件）                        │
│         ▼                                                            │
│  ┌─ PDF 抽取（PyMuPDF）─────────────────────────────────────────┐   │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ 本地 HTTP 服务（仅 127.0.0.1，能力令牌 doc_id）──────────────────┐   │
│  │ GET /view?doc=<doc_id>&page=N&hl=<rects> → HTML 查看页        │   │
│  │ GET /pdf/<token>            → 只读伺服原始 PDF（白名单）     │   │
│  │ GET /assets/…               → pdf.js 静态资源                │   │
│  │ GET /download/<copy_id>    → 批注副本（attachment）          │   │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
         ▲
         │ 只读打开
  用户本地 PDF 文件（源文件永不写入）
```

**组件职责边界**：
- **MCP 工具层**：暴露检索与上下文工具，只处理输入/输出协议与参数校验。
- **会话解析缓存**：负责"一个文件只解析一次"。判等用两级指纹：先以 {真实路径 + 大小 + 修改时间} 做**快速否决**（任一变化即视为需重解析），最终以**解析时顺带计算的全文内容 hash（取前 64 位）** 判定内容是否真的相同——解析本就通读全文，hash 零额外成本，可识别"内容被覆盖但 mtime 未变"的情况。容量上限以**内存预算**为准（默认 1GB，可配）；内部以"累计解析字符数 × 估算每字符占用"近似折算内存占用，逼近预算触发 LRU 淘汰；单份文件超常大时先降级为页级处理。
- **归一化与匹配引擎**：纯函数模块，无状态、可单测（D4 核心，见 §6）。
- **HTTP 服务**：不感知检索逻辑，只负责按参数伺服白名单文件与查看页（§8）。
- **临时文件管理器**：管理批注副本目录与三层清理（§9）。

## 4. 数据流

### 4.1 搜索（核心流程）

```
宿主 LLM 自然语言问题
  → [宿主] 改写为检索词表 terms=[{term, weight?}]（中英同义，语言按字符类型自动判定）
  → [MCP] search(terms, scope, top_k, ...)
       ├─ scope=单文件：解析该文件（缓存未命中时）
       ├─ scope=目录：递归收集 *.pdf → 逐个惰性解析
       ├─ 段落级打分（§6）→ top_k 段落
       └─ 返回 results[]：每项含
            { doc_id, path_display, page, offset_start, offset_end,
              snippet(命中句/段), score, terms_hit, highlight_spans,
               view_url, citation }
  → [宿主] 精读 snippet；不足则调 get_more / read_pages 迭代
  → [宿主] 组织答案，结果中以 markdown 链接呈现 view_url
```

### 4.2 浏览器查看

```
用户在客户端点击 [《文件名》 p.5](http://127.0.0.1:PORT/view?doc=…&page=5&hl=…)
  → HTTP /view 返回 HTML：加载 pdf.js → 打开 /pdf/<token> 原始 PDF
  → 定位到 page 5 → 按 hl= 的矩形列表绘制半透明高亮层
  → 提供"上一处/下一处"高亮导航
```

### 4.3 下载批注副本（可选）

```
宿主调用 download_annotated(doc_id, spans)
  → 临时目录：复制源文件 → PyMuPDF 按 spans 写高亮 annotation
  → 返回 /download/<copy_id> 下载 URL（Content-Disposition: attachment）
  → 副本进入三层清理管理（§9）
```

## 5. MCP 工具设计

传输：stdio。工具命名与描述以"宿主 LLM 会照描述执行"为准撰写。

### 5.1 `search`
按词表对 scope 内 PDF 做段落级检索。
**目录模式语义**：递归收集 `*.pdf`（`recursive` 默认 true）→ 逐文件惰性解析 → 跨文件统一打分、全局合并 top_k；跳过坏文件（非 PDF/损坏/加密）只计数不中断；单次解析达上限时 `truncated=true` 并明示"已扫 N/M 份"，由宿主收窄，**绝不静默只搜一半**。
输入（JSON）：
```jsonc
{
  "scope": {"kind": "file", "path": "D:/docs/a.pdf"}       // 或
  // "scope": {"kind": "directory", "path": "D:/docs", "recursive": true},
  "terms": ["变压器", "过载", "保护", "transformer", "overload"], // 宿主改写词表（推荐）
  "query": "变压器过载保护方案",        // 可选：未传 terms 时服务端做朴素切词回退
  "top_k": 10,
  "highlight": "sentence"               // term | sentence | paragraph
}
```
输出（信封结构）：
```jsonc
{
  "results": [
    {
      "doc_id": "u7s3…",            // 会话内稳定 id（能力令牌）
      "path_display": "a.pdf",
      "page": 5,                     // 1-based
      "offset_start": 12345, "offset_end": 12601,  // 全局字符偏移（原始流）
      "snippet": "……transformer must be …",
      "score": 8.3,
      "terms_hit": ["transformer"],  // 本段落命中了哪些词
      "highlight_spans": [{"page":5,"offset_start":…,"offset_end":…}, …],
      "view_url": "http://127.0.0.1:8765/view?doc=u7s3…&page=5&hl=…",
      "citation": "[《a.pdf》 p.5](http://127.0.0.1:8765/view?doc=u7s3…&page=5&hl=…)"  // 拼好的 markdown 引用
    }
  ],
  "max_score": 8.3,                  // 本次检索最高分（server 计算）
  "term_hits": {                     // 每个检索词在 scope 内命中的段落数（server 统计）
    "比亚迪": 0, "BYD": 0, "2025": 3, "营业收入": 0, "营收": 1, "revenue": 0
  },
  "files_parsed": 1,                 // 本次实际解析/参与的文件数
  "files_scanned": 3,                // 目录模式：实际扫描文件数
  "files_skipped": 1,                // 目录模式：跳过（非 PDF/损坏/加密）数
  "per_file_top": [{"doc_id":"…","path_display":"a.pdf","best_score":8.3}],  // 目录模式：每文件最高分，供二次深搜
  "truncated": false                 // 目录模式：是否因解析上限未扫完；true 时明示已扫/总
}
```
约定：
- `highlight` 决定高亮范围（默认 sentence = 命中词所在句，若命中词跨句则取覆盖全部命中词的最短窗口；paragraph = 整段；term = 仅命中词矩形）。
- `view_url` 的 `hl=` 参数由服务端根据偏移与 `highlight` 模式计算，宿主**无需**关心矩形细节。
- `term_hits` / `max_score` 是**纯可计算的命中统计**，用于让宿主自行判断"词表是否与语料用词对不上、是否该换词重试"。server **不产出任何建议性文本**（无 LLM 依赖）；是否换词、换什么词由宿主决定。
- `search` 工具说明中写入**静态行为契约**（工具描述文本，非运行时建议）：对数值/事实类问题，宿主在作答前应先以 `get_more` / `read_pages` 核对口径、单位、年份，再引用结果。
- 目录模式行为约定：跨文件全局合并 `top_k`；`recursive` 默认 true；坏文件跳过计数不中断；解析上限触发时 `truncated=true` 并附带"已扫 N/M 份"提示。

### 5.2 `cite`
宿主在 `get_more`/`read_pages` 之后，若最终答案落在与 `search` 命中**不同的位置**，用它把"答案真正出处"定位并要一个高亮链接。
输入：`{doc_id, quote, page_hint?}`，其中 `quote` 为宿主从结果里**原样抄回的一小段原文**。
行为：server 对该文档做精确（归一化）子串匹配。
输出：`matches[]`，每项 `{page, offset_start, offset_end, snippet, view_url, citation}`；同一引文出现多次时**返回全部候选**（各带页码与 view_url），由宿主自行选择正确的一个；`page_hint` 可选，用于收窄（如"营业收入"逐页出现时指定某页）。
生成的高亮即这段引文本身（等价 term 模式的精确高亮）。

### 5.3 `get_more`
取命中点周边更大连续文本（snippet 常被截断）。
输入：`{doc_id, page, offset_start, offset_end, context_chars_before/after 默认 600}`。
输出：`{text, page, start/end, 若跨页则返回 pages[]}`（各页附带页码与偏移，便于宿主随后 `cite`）。

### 5.4 `read_pages`
通读指定页区间原文（小文件/低召回时的最强兜底）。
输入：`{doc_id 或 path, from_page, to_page, max_chars?}`。
输出：按页分组的纯文本，每页附带页码（偏移可按需附带）。

### 5.5 `list_documents`
列出 scope 内可检索 PDF。
输入：`{path, recursive}`；输出：`[{path_display, pages?, parsed: bool}]`（未解析文件 pages 可为 null，避免触发解析）。

### 5.6 `download_annotated`
按需生成带批注副本并返回下载 URL。
输入：`{doc_id, spans:[{page, offset_start, offset_end}]}`（spans 直接取自 search 的 `highlight_spans` 或 cite 的定位，已是最终偏移区间）。
输出：`{download_url, temp_path 提示, retention_note}`；副本于**工具调用时**生成，`download_url` 形如 `/download/<copy_id>`。

### 5.7 输出约定
- 每条结果同时给 `view_url`（裸 URL）与 `citation`（server 拼好的 markdown 链接 `[《文件名》 p.页](url)`）；宿主直接嵌入 `citation` 即可，纯文本终端用 `view_url` 复制打开。
- 多个出处按断言逐条列 `citation`，不把链接堆在文末。
- 错误信息结构化（`{error: {code, message, hint}}`），不裸抛堆栈。

## 6. 归一化与匹配引擎（D4 核心）

### 6.1 数据结构（解析产物，仅内存）

```
ParsedDocument:
  file: 真实路径; fingerprint: {size, mtime, hash64}
  pages: [Page]
Page:
  lines: [Line]                    # 阅读顺序
Line:
  text: str                        # 该行文本（原始字符）
  rect: (x0,y0,x1,y1)              # 行矩形（PDF 用户空间点）
  char_count: int                  # 惰性逐字符 bbox 的入口
全局（随 ParsedDocument 构建，常驻量级仅此）:
  orig_chars: 原始字符序列（按行紧凑存储，含 - \n 软连字符 ligature…）
  line_index: 每行 → 全局偏移 的索引
  paragraph_index: {页码, 全局偏移起止}
注意：norm_chars（归一化流）与 norm2orig（双向映射）**不整体常驻**——
按段落惰性构建、用完即弃（B 决策），避免全文档逐字符数组导致内存 O(字符数 × 36B)。
```

### 6.2 归一化规则

对每个原始字符依序变换得到归一化流，并记录映射：
- 小写化（Latin）；
- 常见 ligature 展开：`ﬁ→fi`、`ﬂ→fl`、`ﬀ→ff`、`ﬃ→ffi`、`ﬄ→ffl`；
- 删除软连字符 `U+00AD`、零宽字符、`\r`；
- **删除"行尾 `-` + 换行"**（英文断词连字符，须识别 `-\n` 与 `-\r\n` 且前一字符非空白）；
- 空白序列（空格/制表/换行）折叠为单空格；
- CJK 字符原样保留（子串匹配用），全角字母数字折叠为半角。

### 6.3 匹配

- **中文检索词**：在归一化流做子串匹配（CJK 无词边界）。
- **英文/数字检索词**：词边界正则（`(?<![A-Za-z0-9])…(?![A-Za-z0-9])`），避免 `form` 命中 `transform`。
- 命中集在归一化流上求并集、合并相邻；经 `norm2orig` 反查得到**原始字符区间集合**（可能不连续：断词连字符场景会拆成两段原始区间）。
- 未提供 `terms` 时的朴素回退：对 `query` 按空白切出 Latin 词；CJK 连续段取整段子串与相邻 bigram。

### 6.4 段落级打分

- 段落 = 语义单元（优先按空行/缩进/标题特征切分，退化时按固定 ~500 字符滑窗 + 15% 重叠）。
- 段落自身分 = Σ(命中词权重) + 命中词数加成 + 全文频率 IDF 折扣 + 跨词邻近度小幅加成；段落内多词命中大幅加分。
- 语义命中词位于句首/段首时再加分（命中"sentence 高亮"仍按偏移窗口返回）。
- **页上下文微加成（v1.5，实现顺序排在基础引擎之后，用受控 fixture 验证）**：
  `段落得分 = 段落自身分 + λ × 同页命中信号`；λ 默认 0.1–0.2（可调），"同页命中信号" = 该页所有段落中信息性命中词的加权和。
  目的：让财务报表等表格页整体上浮，使"营业收入 / 研发费用"这类**表格行**能进入 top-k 且行内相对排序正确（否则行段落只命中单词，会被 MD&A 散文句压到很后甚至跌出 top-k）。
  前提约束：
  - 先做**运行页眉/页脚排除**（跨页固定 y 位置检测），避免"比亚迪 2025 年年度报告"式页眉给每页注入噪声；
  - λ 取小值，保证散文句真命中仍稳压表格行"蹭加成"；
  - fixture 必须覆盖：散文句 + 表格页 + 页眉页脚三种形态，断言散文句排序不变、表格行进入 top-k。
- 结果按分排序取 top_k；同分按文件内页序稳定排序。

### 6.5 特殊情况矩阵

| 场景 | 处理 |
|---|---|
| 英文断词连字符跨行 | 归一化删除 `-\n`；映射回两段原始区间；高亮成两段相邻矩形 |
| 短语跨行/跨页 | 归一化流连续故可命中；高亮按页拆分 |
| 中文跨行 | 子串匹配 + 空白折叠后天然连续 |
| 双栏排版 | 按 PyMuPDF 阅读顺序逐行入流；矩形按行合并，不产生跨栏大矩形 |
| ligature/全角/软连字符 | 归一化表统一处理 |
| 拼写错误/OCR 垃圾 | 不做模糊匹配（语料为文字层 PDF）；漏召回由宿主换词重搜 |

### 6.6 向量升级位

段落表（内存）预留 `vector: float[] | null` 字段与"相似度召回路"的接口签名；当前恒为 null，不引入任何模型依赖。将来启用时仅新增一路召回 + RRF 融合，工具 schema 不变。

## 7. 高亮生成细节

1. `highlight_spans`（原始偏移区间）来自 search 结果，无需重新解析即可换算到 {页码, 行}（页内偏移已知）。
2. 对涉及的页**惰性**重取 PyMuPDF `rawdict`（同文件同版本解析器，结果确定，字符与偏移一致），取每字符 bbox；解析单页为毫秒级，不做全文档常驻。
3. 命中字符按 {页码, 行} 分组，同一行内合并为一个矩形，外扩 1pt padding；**不跨行合并**——每行各自成矩形（跨行命中即多个相邻矩形）。
4. 生成 `rects: [page → [rect,…]]`：
   - `/view` 模式：rects 序列化进 `hl=` URL 参数，由前端绘制；
   - `download_annotated` 模式：同一 rects 集以 PyMuPDF 高亮 annotation 写入副本。
5. 坐标空间统一为 PDF 用户空间点（PyMuPDF page.rect 与 pdf.js 基础坐标一致，前端按 viewport scale 换算）。

## 8. 本地 HTTP 服务与查看页

- 绑定 `127.0.0.1`，端口取空闲随机端口；仅随 MCP 进程存活。
- **能力令牌（capability token）**：文件在会话中首次被解析时铸一枚随机令牌（≥128bit），**`doc_id` 即该令牌**；所有伺服 URL 携带 `doc_id`；未知/失效令牌一律 404（进程重启后旧链接失效属预期，§10 有对应错误提示）。
- **白名单** = 本进程铸过令牌的文件集合：按 `doc_id → 真实路径` 精确映射伺服，仅限"解析过且仍在缓存/指纹表中"的文件；不做目录列举；不跟随符号链接出白名单。
- 路由：
  - `/view?doc=<doc_id>&page=N&hl=<urlencoded rects>` → HTML 查看页（内联矩形）
  - `/view?doc=<doc_id>&page=N&hlid=<短随机 id>` → 同上（矩形数超过阈值时用；数据在内存映射里）
  - `/hl/<hlid>` → 返回该 hlid 对应的矩形 JSON（供查看页二次获取）
  - `/pdf/<doc_id>` → 原始 PDF，`Content-Type: application/pdf`，只读
  - `/assets/…` → 打包的 pdf.js 静态资源（离线可用）
  - `/download/<copy_id>` → 批注副本（attachment；copy_id 为工具调用时铸的副本能力令牌）
- `hl=` 内联 vs `hlid=`：默认内联；当矩形数 > 阈值（40）时，server 将矩形列表存入内存映射、URL 改用短随机 `hlid`，查看页经 `/hl/<hlid>` 取回同一份矩形——两者送达浏览器的矩形数据完全一致，仅传输通道不同；URL 恒短且无新持久状态。
- 查看页行为：pdf.js 打开 `/pdf/<token>`；`page=N` 定位；对矩形列表（来自 `hl=` 或 `/hl/<hlid>`）中该页矩形画半透明高亮层（可开关）；"上一处/下一处"按钮遍历全部矩形跨页跳转；页面标题显示 `path_display`。
- pdf.js 资源：随 Python 包分发 `pdfjs-dist`（构建版静态目录），不依赖 CDN。

## 9. 生命周期与清理（D6）

| 对象 | 位置 | 产生时机 | 清理 |
|---|---|---|---|
| 批注副本 | 系统临时目录 `pdf-nl-search-mcp/` | `download_annotated` | 进程退出即清空（atexit/信号）+ TTL 24h 扫描 + 上限 20 份按最旧淘汰 |
| 会话解析缓存 | 进程内存 | search 惰性解析 | LRU 内存预算（默认 1GB，可配）；进程退出即失 |
| txt / 磁盘检索索引 | — | 永不产生 | — |

约定：server 永不写回源文件所在目录、永不修改源文件；下载副本仅作临时载体，用户如需留存自行另存。

## 10. 错误处理

原则：所有错误结构化 `{error: {code, message, hint}}`，不裸抛堆栈；分两类通道——**工具调用错误**经 MCP JSON-RPC 返回给宿主，**HTTP 错误**（浏览器点链接）返回友好错误页/404。

- 文件不存在/被移动/权限不足：`file_unavailable`，hint 建议重新 `list_documents`。
- scope/参数错误（`kind` 与路径不符、`top_k≤0`、`spans` 偏移越界、`page_hint` 超页数）：`invalid_args`，message 点明具体参数。
- 加密 PDF（有 owner/user 密码）：`pdf_encrypted`；空密码可解则透明处理并提示。
- 损坏/非 PDF：`pdf_unparseable`。
- 无文字层（扫描版）：`no_text_layer`，明确不支持 OCR。
- 会话重启后旧 URL token 失效：`token_expired`，提示重新搜索获取新链接。
- `cite` 引文未匹配到原文（宿主抄错/归一化差异）：`quote_not_found`，hint 提示核对引文或改用 `read_pages`。
- 单文件解析超限（超大 PDF）或内存逼近上限：先降级为页级抽取，仍不足则报 `resource_limit`。
- 目录搜索中单个坏文件只跳过计数（`files_skipped`），不中断整次搜索。

## 11. 测试策略

- **单元（引擎，最高优先）**：归一化与映射——fixtures 覆盖：断词连字符、跨行短语、跨页短语、中文子串、ligature、软连字符、全角、双栏行序、词边界防误命中（form/transform）。属性：任意归一化位置反查原始区间不越界、顺序单调。
- **单元（打分）**：多词加权、IDF、邻近加成、同分稳定排序；页上下文微加成的回归 fixture 见 §6.4（散文句排序不变、表格行进 top-k、页眉页脚不注噪）。
- **单元（cite）**：`quote` 命中；`quote_not_found`（故意抄错引文报对码）；`page_hint` 收窄；同一引文多处出现时返回全部候选。
- **单元（HTTP/清理）**：token 鉴权、白名单外 404、TTL/上限淘汰逻辑（用短 TTL 注入测试）。
- **集成**：PyMuPDF 生成受控测试 PDF（含断词/跨页/中文/双栏样例，以及**已知坐标的文本**）→ search 命中并核对 page/offset；**断言高亮矩形落在预期行/范围内**（不只"有 rect"）；`/view` 页面用无头浏览器冒烟（可选）；`download_annotated` 产物用 PyMuPDF 复核 annotation 数量与 rect。
- **端到端**：经 mcp Python SDK 以 stdio 调用全工具链（含 `cite`）。
- **性能**：解析吞吐基线（页/秒）、千页 PDF 首次搜索耗时、命中生成高亮耗时（目标：千页内首次搜索 < 5s，命中→高亮 < 1s，不满足则记录为优化项）。

## 12. 部署与接入

- 运行：Python 3.10+；`uv` 项目管理；依赖：`mcp`、`PyMuPDF`；pdf.js 静态资源打包。
- **分发形态（双轨）**：
  - **源码 + uv（主）**：同事 `git clone` → `uv sync` → 配置 `uv run pdf-nl-search-mcp`；成熟后发布 PyPI/私有制品库，同事改 `uv tool install pdf-nl-search-mcp`。同事仅需装 uv（uv 自动管理 Python 3.10+）。
  - **独立可执行文件（可选）**：PyInstaller 打包，供不愿装 uv 的同事零环境使用；三平台分别构建、体积较大，pdf.js 静态资源一并内嵌。
- 传输：stdio；**stdout 仅走 JSON-RPC，日志一律去 stderr 或文件**（避免污染协议）。
- 本地 HTTP 端口：启动时取随机空闲端口（不可配，无固定端口需求）。
- 环境变量（均有默认值，零配置即可用）：

| 环境变量 | 默认 | 用途 |
|---|---|---|
| `PDFNL_CACHE_MB` | 1024 | 会话解析缓存内存预算（LRU 上限，§3） |
| `PDFNL_SEARCH_LIMIT` | 20000000（字符） | 单次 `search` 的解析上限（目录搜索超限即 `truncated=true`，§5.1） |
| `PDFNL_LOG_LEVEL` | info | 日志级别（写 stderr），调试用 |
| `PDFNL_TMP_DIR` | 系统临时目录 | 批注副本存放目录（§9，几乎无需改） |

- MCP 客户端配置示例（三端同 schema，`env` 字段注入环境变量）：
  ```jsonc
  // Claude Code: .mcp.json
  { "mcpServers": { "pdf-nl-search": {
      "command": "uv", "args": ["run", "pdf-nl-search-mcp"],
      "env": { "PDFNL_CACHE_MB": "1024" } } } }
  // opencode: opencode.json 的 mcp 段；VSCode(Copilot/Cline/Continue): .mcp.json —— 同结构
  ```
- 首次使用无索引构建步骤：语料即用户机器上任意路径，搜索时按 scope 惰性解析。
- Windows 注意：`uv` 可能写作 `uv.exe`（或用绝对路径）；路径统一绝对路径；URL 编码路径；pdf.js 本地伺服无跨域问题。

## 13. 超出范围（YAGNI）

- OCR / 扫描版支持（无文字层 PDF 明确报错）。
- embedding / 向量检索（预留升级位，本期不做）。
- 目录监视与自动索引（与 D3 冲突）。
- 多用户/远程访问/鉴权体系（仅本机 token）。
- 批注编辑、书签、笔记等文档管理功能。

## 14. 验收标准（映射需求）

| # | 需求 | 验收 |
|---|---|---|
| 1 | 搜索文字版 PDF | 对单文件与目录均能返回命中 |
| 2 | 自然语言语义搜索 | 宿主 LLM 改写词表后，同义/中英改述查询可命中目标段（测试语料验证） |
| 3 | 原文出处 | 结果含 path/page/偏移/片段 |
| 4 | 链接跳页 | 点击 `view_url` 在浏览器打开并定位于对应页 |
| 5 | 出处高亮可见 | 查看页高亮层准确覆盖命中内容，跨浏览器一致 |
| 6 | 单文件/目录 | scope 两种形态 |
| 7 | 多客户端 | 三个目标客户端的接入配置可用 |
| 8 | 最终答案位置可引用 | 宿主经 `cite` 可对 `search` 命中之外的位置产出高亮链接 |
| — | 不污染源文件 | 源文件只读，唯一落盘临时物按三层清理 |

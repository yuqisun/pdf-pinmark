from dataclasses import dataclass, field

Rect = tuple[float, float, float, float]


@dataclass
class Line:
    text: str
    rect: Rect
    global_start: int        # 首字符在 orig_text 中的偏移
    page_line_index: int     # 页内行序号（0-based）
    words: list = field(default_factory=list)  # [(rect, start, end), ...] 每词矩形与全局偏移区间


@dataclass
class Page:
    page_no: int             # 0-based
    rect: Rect
    global_start: int        # 页首字符在 orig_text 中的偏移
    char_count: int          # 页内字符数（不含每行末尾 \n）
    lines: list[Line] = field(default_factory=list)


@dataclass
class Paragraph:
    page_no: int
    start: int               # 全局偏移（含）
    end: int                 # 全局偏移（不含）


@dataclass
class ParsedDocument:
    path: str
    fingerprint: str         # hash64（16 hex）
    orig_text: str
    pages: list[Page] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    line_ends: set = field(default_factory=set)  # 每行末字符的全局偏移集合


@dataclass
class SearchHit:
    doc_id: str
    path_display: str
    page: int                # 1-based
    offset_start: int
    offset_end: int
    snippet: str
    score: float
    terms_hit: list
    highlight_spans: list
    view_url: str
    citation: str

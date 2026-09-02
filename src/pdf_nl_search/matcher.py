import re

CJK_RANGES = [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF)]


def _is_cjk(c: str) -> bool:
    o = ord(c)
    return any(lo <= o <= hi for lo, hi in CJK_RANGES)


def is_cjk_term(term: str) -> bool:
    return any(_is_cjk(c) for c in term)


def find_terms(norm_text: str, term: str, cjk: bool) -> list[tuple[int, int]]:
    """返回归一化文本中命中的 [start,end) 列表。"""
    pat = re.escape(term)
    flags = re.IGNORECASE
    if not cjk:
        pat = r"(?<![A-Za-z0-9])" + pat + r"(?![A-Za-z0-9])"
    return [m.span() for m in re.finditer(pat, norm_text, flags)]


def fallback_terms(query: str) -> list[str]:
    """无 terms 时的朴素回退：Latin 词 + CJK 整段子串 + CJK bigram。"""
    terms = re.findall(r"[A-Za-z0-9]+", query)
    for run in re.findall(r"[\u4e00-\u9fff]+", query):
        terms.append(run)
        terms += [run[i : i + 2] for i in range(len(run) - 1)]
    return terms

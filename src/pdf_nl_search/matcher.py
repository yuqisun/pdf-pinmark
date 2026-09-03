import re

try:
    from opencc import OpenCC
    _S2T = OpenCC("s2t")
    _T2S = OpenCC("t2s")
except Exception:  # opencc 未安装时降级为不做简繁转换
    _S2T = _T2S = None

CJK_RANGES = [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF)]


def _is_cjk(c: str) -> bool:
    o = ord(c)
    return any(lo <= o <= hi for lo, hi in CJK_RANGES)


def is_cjk_term(term: str) -> bool:
    return any(_is_cjk(c) for c in term)


def cjk_variants(s: str) -> list[str]:
    """CJK 字符串的简/繁变体（含原形，去重保持顺序）；非 CJK 返回原形。

    用于让简体查询命中繁体文本（反之亦然）。opencc 未安装时返回原形。
    """
    if not is_cjk_term(s) or _S2T is None:
        return [s]
    seen = []
    for v in (s, _S2T.convert(s), _T2S.convert(s)):
        if v not in seen:
            seen.append(v)
    return seen


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

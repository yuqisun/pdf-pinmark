from pdf_nl_search.normalize import normalize_range


def n(text, line_ends=()):
    s, m = normalize_range(text, 0, len(text), set(line_ends))
    return s, m


def test_lowercase():
    s, _ = n("ABC")
    assert s == "abc"


def test_ligature_expand():
    s, _ = n("ﬁ ﬂ ﬀ ﬃ ﬄ")
    assert s == "fi fl ff ffi ffl"


def test_remove_soft_hyphen_and_cr():
    s, _ = n("a\u00adb\r")
    assert s == "ab"


def test_hyphen_at_line_end_removed():
    # "transfor-" 连字符在 index 8（行尾），后接 \n
    text = "transfor-\nmer"
    s, m = n(text, line_ends={8})
    assert s == "transformer"
    # 归一化后 "transformer" 的 'm'（norm index 8）应映射回原始 'm'（index 10）
    assert m[8] == 10


def test_hyphen_with_crlf_removed():
    text = "transfor-\r\nmer"
    s, m = n(text, line_ends={8})
    assert s == "transformer"
    assert m[8] == 11


def test_dash_after_space_kept():
    text = "word -\nnext"
    s, _ = n(text, line_ends={5})
    assert s == "word - next"


def test_whitespace_collapse():
    s, _ = n("a \t\n  b")
    assert s == "a b"


def test_fullwidth_fold():
    s, _ = n("ＡＢＣ１２３")
    assert s == "abc123"


def test_map_monotonic_and_in_bounds():
    text = "Transfor-\nmer 2025 ﬁ"
    s, m = n(text, line_ends={8})
    assert len(s) == len(m)
    assert all(0 <= x < len(text) for x in m)
    assert m == sorted(m)

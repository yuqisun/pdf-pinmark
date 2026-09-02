from pdf_nl_search.matcher import is_cjk_term, find_terms, fallback_terms


def test_cjk_substring():
    assert is_cjk_term("营业收入")
    s = "2025年，营业收入9,328.5亿元"
    assert find_terms(s, "营业收入", True) == [(6, 10)]


def test_latin_word_boundary():
    assert not is_cjk_term("form")
    s = "transform the form now"
    assert find_terms(s, "form", False) == [(14, 18)]


def test_latin_matches_case_insensitive():
    assert find_terms("Revenue is here", "revenue", False) == [(0, 7)]


def test_fallback_terms_mixed():
    t = fallback_terms("比亚迪 BYD 营收")
    assert "比亚迪" in t and "营收" in t and "BYD" in t
    assert "亚迪" in t  # bigram

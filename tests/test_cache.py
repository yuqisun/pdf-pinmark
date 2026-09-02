from pdf_nl_search.cache import SessionCache
from pdf_nl_search.models import ParsedDocument


def _doc(path, nchars):
    return ParsedDocument(path=path, fingerprint="h", orig_text="x" * nchars)


def test_hit_and_eviction():
    c = SessionCache(char_budget=12)  # 4+4+8=16 超预算，淘汰最旧 /a 后 12≤12 停，保留 /b
    c.put("/a", 1, 100, "h1", _doc("/a", 4))
    c.put("/b", 2, 200, "h2", _doc("/b", 4))
    assert c.get("/a", 1, 100) is not None
    assert c.get("/b", 2, 200) is not None
    c.put("/c", 3, 300, "h3", _doc("/c", 8))  # 超预算，淘汰最久未用的 /a
    assert c.get("/a", 1, 100) is None
    assert c.get("/b", 2, 200) is not None


def test_mtime_change_is_miss():
    c = SessionCache(char_budget=100)
    c.put("/a", 1, 100, "h1", _doc("/a", 4))
    assert c.get("/a", 1, 100) is not None
    assert c.get("/a", 1, 101) is None  # mtime 变了 → 视为需重解析

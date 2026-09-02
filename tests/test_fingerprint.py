from pdf_nl_search import fingerprint


def test_fingerprint_stable(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"hello world")
    s1, m1, h1 = fingerprint.of(p)
    s2, m2, h2 = fingerprint.of(p)
    assert (s1, m1, h1) == (s2, m2, h2)
    assert s1 == 11
    assert len(h1) == 16  # hash64 = 16 hex chars


def test_fingerprint_changes_with_content(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"one")
    _, _, h1 = fingerprint.of(p)
    p.write_bytes(b"two")
    _, _, h2 = fingerprint.of(p)
    assert h1 != h2

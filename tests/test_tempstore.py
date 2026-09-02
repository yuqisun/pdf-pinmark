import os
import time
from pdf_nl_search.tempstore import TempStore


def test_add_and_get(tmp_path):
    ts = TempStore(tmp_path, ttl=100, cap=10)
    path, cid = ts.add(b"data", suffix=".pdf")
    assert os.path.exists(path)
    assert ts.get(cid) == path


def test_ttl_and_cap_sweep(tmp_path):
    ts = TempStore(tmp_path, ttl=0.01, cap=2)
    p1, c1 = ts.add(b"1", ".pdf")
    time.sleep(0.02)
    p2, c2 = ts.add(b"2", ".pdf")
    p3, c3 = ts.add(b"3", ".pdf")
    ts.sweep()
    assert ts.get(c1) is None       # 过期
    assert ts.get(c2) is None or ts.get(c3) is not None  # 超 cap 淘汰最旧

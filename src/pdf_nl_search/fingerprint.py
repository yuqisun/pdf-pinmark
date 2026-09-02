import hashlib
import os


def of(path) -> tuple[int, int, str]:
    """返回 (size, mtime_ns, hash64)。hash64 = sha256 前 64 位（16 hex）。"""
    st = os.stat(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return (st.st_size, st.st_mtime_ns, h.hexdigest()[:16])


def quick(path) -> tuple[int, int]:
    """快速否决用：size + mtime，不做内容 hash。"""
    st = os.stat(path)
    return (st.st_size, st.st_mtime_ns)

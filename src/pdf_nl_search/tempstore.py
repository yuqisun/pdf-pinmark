import os
import secrets
import time
from collections import OrderedDict


class TempStore:
    def __init__(self, tmp_dir: str, ttl: float = 86400.0, cap: int = 20):
        os.makedirs(tmp_dir, exist_ok=True)
        self.dir = tmp_dir
        self.ttl = ttl
        self.cap = cap
        self._map: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def add(self, data: bytes, suffix: str) -> tuple[str, str]:
        cid = secrets.token_urlsafe(16)
        path = os.path.join(self.dir, cid + suffix)
        with open(path, "wb") as f:
            f.write(data)
        self._map[cid] = (path, time.time())
        self._map.move_to_end(cid)
        self.sweep()
        return path, cid

    def get(self, cid: str) -> str | None:
        e = self._map.get(cid)
        if e is None:
            return None
        path, _ = e
        if not os.path.exists(path):
            self._map.pop(cid, None)
            return None
        return path

    def sweep(self):
        now = time.time()
        for cid in list(self._map):
            path, ts = self._map[cid]
            if now - ts > self.ttl:
                self._remove(cid)
        while len(self._map) > self.cap:
            oldest = next(iter(self._map))  # 最旧 key，交给 _remove 统一 pop+删文件
            self._remove(oldest)

    def _remove(self, cid):
        e = self._map.pop(cid, None)
        if e:
            path, _ = e
            try:
                os.remove(path)
            except OSError:
                pass

    def cleanup_all(self):
        for cid in list(self._map):
            self._remove(cid)

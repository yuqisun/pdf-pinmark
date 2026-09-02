from collections import OrderedDict
from .models import ParsedDocument


class SessionCache:
    def __init__(self, char_budget: int):
        self._budget = char_budget
        self._total = 0
        self._map: OrderedDict[str, dict] = OrderedDict()

    def get(self, path: str, size: int, mtime: int) -> ParsedDocument | None:
        e = self._map.get(path)
        if e is None:
            return None
        if (e["size"], e["mtime"]) != (size, mtime):
            self._drop(path)
            return None
        self._map.move_to_end(path)
        return e["doc"]

    def put(self, path: str, size: int, mtime: int, hash64: str, doc: ParsedDocument):
        self._map[path] = {"size": size, "mtime": mtime, "hash": hash64,
                           "doc": doc, "chars": len(doc.orig_text)}
        self._total += len(doc.orig_text)
        self._map.move_to_end(path)
        while self._total > self._budget and self._map:
            _, entry = self._map.popitem(last=False)
            self._total -= entry["chars"]

    def _drop(self, path: str):
        e = self._map.pop(path, None)
        if e:
            self._total -= e["chars"]

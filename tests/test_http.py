import json
import threading
import urllib.error
import urllib.request
from pdf_nl_search.http import start_server
from pdf_nl_search.session import Session
from pdf_nl_search.config import Config
from tests.conftest import make_pdf


def _serve(session):
    srv, port = start_server(session, "127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return port, srv


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        # urllib 对非 2xx 响应抛 HTTPError；回环测试需取得其状态码与响应体
        return e.code, e.read()


def test_unknown_doc_404(tmp_path):
    s = Session(Config(1024, 10000, "info", str(tmp_path / "tmp")))
    port, srv = _serve(s)
    st, _ = _get(f"http://127.0.0.1:{port}/pdf/nonexistent")
    assert st == 404
    srv.shutdown()


def test_known_doc_serves_pdf(tmp_path):
    p = make_pdf(tmp_path / "d.pdf", [["hello"]])
    s = Session(Config(1024, 10000, "info", str(tmp_path / "tmp")))
    doc_id, _ = s.get_or_parse(str(p))
    port, srv = _serve(s)
    st, body = _get(f"http://127.0.0.1:{port}/pdf/{doc_id}")
    assert st == 200
    assert body[:4] == b"%PDF"
    srv.shutdown()


def test_hl_route_roundtrip(tmp_path):
    s = Session(Config(1024, 10000, "info", str(tmp_path / "tmp")))
    s.hl_store["abc"] = {0: [(1.0, 2.0, 3.0, 4.0)]}
    port, srv = _serve(s)
    st, body = _get(f"http://127.0.0.1:{port}/hl/abc")
    assert st == 200
    assert json.loads(body)["0"][0] == [1.0, 2.0, 3.0, 4.0]
    srv.shutdown()

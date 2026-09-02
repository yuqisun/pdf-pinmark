import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def start_server(session, host="127.0.0.1", port=0):
    srv = ThreadingHTTPServer((host, port), make_handler(session))
    session.http_port = srv.server_address[1]
    return srv, srv.server_address[1]


def make_handler(session):
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.path)
            if u.path == "/view":
                q = parse_qs(u.query)
                doc = q.get("doc", [""])[0]
                if doc not in session.doc_by_id:
                    return self._send(404, b"link expired", "text/plain; charset=utf-8")
                body = _render_viewer(doc, q.get("page", ["1"])[0],
                                      q.get("hl", [""])[0], q.get("hlid", [""])[0])
                return self._send(200, body.encode("utf-8"), "text/html; charset=utf-8")
            if u.path.startswith("/pdf/"):
                doc = u.path[len("/pdf/"):]
                if doc not in session.doc_by_id:
                    return self._send(404, b"not found", "text/plain")
                with open(session.doc_by_id[doc].path, "rb") as f:
                    return self._send(200, f.read(), "application/pdf")
            if u.path.startswith("/hl/"):
                hlid = u.path[len("/hl/"):]
                rects = session.hl_store.get(hlid)
                if rects is None:
                    return self._send(404, b"not found", "text/plain")
                return self._send(200, json.dumps(rects).encode(), "application/json")
            if u.path.startswith("/download/"):
                cid = u.path[len("/download/"):]
                path = session.copy_store.get(cid)
                if path is None or not os.path.exists(path):
                    return self._send(404, b"not found", "text/plain")
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", "attachment")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if u.path.startswith("/assets/"):
                rel = u.path[len("/assets/"):]
                p = os.path.normpath(os.path.join(assets_dir, rel))
                if not p.startswith(assets_dir) or not os.path.isfile(p):
                    return self._send(404, b"not found", "text/plain")
                ctype = "application/javascript" if p.endswith((".js", ".mjs")) else "text/html; charset=utf-8"
                with open(p, "rb") as f:
                    return self._send(200, f.read(), ctype)
            self._send(404, b"not found", "text/plain")

    return Handler


def _render_viewer(doc, page, hl, hlid):
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>PDF 高亮查看</title></head>
<body><div id="app">正在加载…</div>
<script type="module" src="/assets/viewer.js"></script>
<script>window.__VIEW={{"doc":{json.dumps(doc)},"page":{page},"hl":{json.dumps(hl)},"hlid":{json.dumps(hlid)}}};</script>
</body></html>"""

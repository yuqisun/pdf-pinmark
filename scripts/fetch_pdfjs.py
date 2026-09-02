"""下载 pdf.js 静态资源到 src/pdf_nl_search/assets/pdfjs/（离线查看用，Apache-2.0）。

带重试、下载大小校验与多 CDN 回退（jsdelivr → unpkg）。

在能联网的机器上运行：python scripts/fetch_pdfjs.py
"""

import os
import time
import urllib.request

VERSION = "4.7.76"
FILES = ("pdf.mjs", "pdf.worker.mjs")
CDNS = (
    f"https://cdn.jsdelivr.net/npm/pdfjs-dist@{VERSION}/build/",
    f"https://unpkg.com/pdfjs-dist@{VERSION}/build/",
)
OUT = os.path.join(os.path.dirname(__file__), "..", "src", "pdf_nl_search", "assets", "pdfjs")


def download(url: str, dest: str, retries: int = 3) -> int:
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            if len(data) < 1024:  # 过小视为被截断
                raise IOError(f"downloaded only {len(data)} bytes (truncated)")
            with open(dest, "wb") as f:
                f.write(data)
            return len(data)
        except Exception as e:
            print(f"    attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
            else:
                raise


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in FILES:
        dest = os.path.join(OUT, name)
        last_err = None
        for base in CDNS:
            url = base + name
            try:
                n = download(url, dest)
                print(f"ok: {name} ({n} bytes) <- {url}")
                last_err = None
                break
            except Exception as e:
                last_err = e
                print(f"  failed from {base}: {e}")
        if last_err is not None:
            raise SystemExit(f"FAILED to download {name}: {last_err}")
    print("done ->", os.path.abspath(OUT))


if __name__ == "__main__":
    main()

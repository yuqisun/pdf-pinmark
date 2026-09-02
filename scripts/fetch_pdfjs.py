"""下载 pdf.js 静态资源到 src/pdf_nl_search/assets/pdfjs/（离线查看用，Apache-2.0）。

在能联网的机器上运行：python scripts/fetch_pdfjs.py
"""

import os
import urllib.request

VERSION = "4.7.76"
BASE = f"https://cdn.jsdelivr.net/npm/pdfjs-dist@{VERSION}/build/"
OUT = os.path.join(os.path.dirname(__file__), "..", "src", "pdf_nl_search", "assets", "pdfjs")


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in ("pdf.mjs", "pdf.worker.mjs"):
        url = BASE + name
        dest = os.path.join(OUT, name)
        print("downloading", url)
        urllib.request.urlretrieve(url, dest)
    print("done ->", os.path.abspath(OUT))


if __name__ == "__main__":
    main()

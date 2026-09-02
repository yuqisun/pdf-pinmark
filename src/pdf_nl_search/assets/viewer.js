// PDF 高亮查看页前端：加载 pdf.js、渲染页面、按矩形绘制高亮层、上下处导航。
import * as pdfjsLib from "/assets/pdfjs/pdf.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/assets/pdfjs/pdf.worker.mjs";

const cfg = window.__VIEW || { doc: "", page: 1, hl: "", hlid: "" };
let pdf = null;
let current = Number(cfg.page) || 1;
let rectMap = {};

function parseHl(hl) {
  const map = {};
  for (const part of String(hl || "").split(";")) {
    if (!part) continue;
    const i = part.indexOf(":");
    const page = part.slice(0, i);
    const rect = part.slice(i + 1).split(",").map(Number);
    (map[page] = map[page] || []).push(rect);
  }
  return map;
}

async function loadRects() {
  if (cfg.hl) return parseHl(cfg.hl);
  if (cfg.hlid) {
    const r = await fetch("/hl/" + cfg.hlid);
    return await r.json();
  }
  return {};
}

function clearHighlights() {
  const layer = document.getElementById("hl");
  while (layer.firstChild) layer.removeChild(layer.firstChild);
}

async function renderPage(n) {
  if (!pdf) return;
  current = n;
  const page = await pdf.getPage(n);
  const viewport = page.getViewport({ scale: 1.5 });
  const canvas = document.getElementById("cv");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext("2d");
  await page.render({ canvasContext: ctx, viewport }).promise;

  clearHighlights();
  const mine = rectMap[String(n)] || rectMap[n] || [];
  const layer = document.getElementById("hl");
  layer.style.width = viewport.width + "px";
  layer.style.height = viewport.height + "px";
  for (const rect of mine) {
    // PDF 用户空间坐标 → 当前缩放下的 viewport 坐标
    const [x0, y0, x1, y1] = viewport.convertToViewportRectangle(rect);
    const div = document.createElement("div");
    div.style.cssText = "position:absolute;background:rgba(255,230,80,.45);mix-blend-mode:multiply;border:1px solid rgba(230,180,0,.7)";
    div.style.left = x0 + "px";
    div.style.top = y0 + "px";
    div.style.width = (x1 - x0) + "px";
    div.style.height = (y1 - y0) + "px";
    layer.appendChild(div);
  }
  const info = document.getElementById("pageinfo");
  if (info) info.textContent = "第 " + n + " / " + pdf.numPages + " 页";
}

document.getElementById("prev").onclick = () => renderPage(Math.max(1, current - 1));
document.getElementById("next").onclick = () => renderPage(Math.min(pdf.numPages, current + 1));

pdfjsLib.getDocument("/pdf/" + cfg.doc).promise
  .then((p) => { pdf = p; return loadRects(); })
  .then((m) => { rectMap = m; return renderPage(current); });

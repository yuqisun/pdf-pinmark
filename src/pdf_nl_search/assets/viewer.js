// PDF 高亮查看页前端：加载 pdf.js、渲染页面、绘制两层高亮（上下文浅框 + 关键词黄底橙框）、上下处导航。
import * as pdfjsLib from "/assets/pdfjs/pdf.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/assets/pdfjs/pdf.worker.mjs";

const cfg = window.__VIEW || { doc: "", page: 1, hl: "", khl: "", hlid: "" };
let pdf = null;
let current = Number(cfg.page) || 1;
let contextMap = {};  // 页号 -> [rect]（浅色框，标记整句/整段范围）
let termMap = {};     // 页号 -> [rect]（黄底橙框，标记命中关键词）

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
  if (cfg.hlid) {
    const r = await fetch("/hl/" + cfg.hlid);
    const data = await r.json();
    return { context: data.context || {}, terms: data.terms || {} };
  }
  return { context: parseHl(cfg.hl), terms: parseHl(cfg.khl) };
}

function clearHighlights() {
  const layer = document.getElementById("hl");
  while (layer.firstChild) layer.removeChild(layer.firstChild);
}

function drawRect(layer, rect, scale, style) {
  const [x0, y0, x1, y1] = rect;
  const div = document.createElement("div");
  div.style.cssText = "position:absolute;" + style;
  div.style.left = (x0 * scale) + "px";
  div.style.top = (y0 * scale) + "px";
  div.style.width = ((x1 - x0) * scale) + "px";
  div.style.height = ((y1 - y0) * scale) + "px";
  layer.appendChild(div);
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
  const layer = document.getElementById("hl");
  layer.style.width = viewport.width + "px";
  layer.style.height = viewport.height + "px";
  const scale = viewport.scale;
  const CONTEXT_STYLE = "background:rgba(150,180,255,.13);outline:1.5px dashed rgba(90,120,200,.55);outline-offset:-1px;border-radius:2px;";
  const TERM_STYLE = "background:rgba(255,225,0,.55);mix-blend-mode:multiply;outline:2px solid rgba(255,140,0,.9);outline-offset:-2px;border-radius:1px;";
  // 先画上下文浅框，再画关键词黄底橙框（关键词覆盖在上层）
  for (const rect of (contextMap[String(n)] || contextMap[n] || [])) {
    drawRect(layer, rect, scale, CONTEXT_STYLE);
  }
  for (const rect of (termMap[String(n)] || termMap[n] || [])) {
    drawRect(layer, rect, scale, TERM_STYLE);
  }
  const info = document.getElementById("pageinfo");
  if (info) info.textContent = "第 " + n + " / " + pdf.numPages + " 页";
}

document.getElementById("prev").onclick = () => renderPage(Math.max(1, current - 1));
document.getElementById("next").onclick = () => renderPage(Math.min(pdf.numPages, current + 1));

pdfjsLib.getDocument("/pdf/" + cfg.doc).promise
  .then((p) => { pdf = p; return loadRects(); })
  .then((m) => { contextMap = m.context; termMap = m.terms; return renderPage(current); });

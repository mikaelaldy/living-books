// Reader. Pages are data; Beam's code runs only from this site's own book files.
import { PopupStage } from './popup.js';

const q = new URLSearchParams(location.search);
const BOOK = q.get('book') || 'peter-rabbit';
const $ = s => document.querySelector(s);
const canvasBox = $('#stage'), text = $('#text'), textWrap = $('#textWrap'), pager = $('#pager'), title = $('#title');
// Phones and small machines animate at 30 fps, which halves the work per second.
const LITE = matchMedia('(pointer: coarse)').matches || (navigator.hardwareConcurrency || 8) <= 4;
let pages = [], index = 0, stage = null, flat = null, start = 0, mode = q.get('mode') || 'popup';
let tx = 0, ty = 0, cx = 0, cy = 0, frames = 0, token = 0, last = 0;
const cache = new Map();

const pageUrl = i => `data/${BOOK}/pages/${String(i + 1).padStart(2, '0')}.json`;
const getPage = i => { if (!cache.has(i)) cache.set(i, fetch(pageUrl(i)).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })); return cache.get(i); };

function freshCanvas() {
  canvasBox.querySelector('canvas')?.remove();
  const c = document.createElement('canvas'); c.setAttribute('aria-label', 'Animated scene for this page');
  canvasBox.prepend(c); return c;
}
function useFlat() {
  stage?.dispose(); stage = null; mode = 'flat';
  const c = freshCanvas(), s = LITE ? 1.5 : 2; c.width = 390 * s; c.height = 520 * s; flat = { ctx: c.getContext('2d'), s };
}
function useStage() {
  try { stage = new PopupStage(freshCanvas()); }
  catch (e) { console.warn('WebGL unavailable, using flat pages', e); useFlat(); }
}
function updateMore() { textWrap.classList.toggle('more', text.scrollHeight - text.scrollTop - text.clientHeight > 8); }

async function show(i) {
  index = Math.max(0, Math.min(pages.length - 1, i));
  const me = ++token;
  canvasBox.classList.add('turning'); text.classList.add('turning');
  let rec;
  try { rec = await getPage(index); } catch (e) { text.textContent = 'This page could not load. Check your connection and try again.'; text.classList.remove('turning'); return; }
  if (me !== token) return;
  await new Promise(r => setTimeout(r, 120));
  if (me !== token) return;
  text.textContent = rec.text; text.scrollTop = 0;
  pager.textContent = `${index + 1} / ${pages.length}`;
  $('#bar i').style.width = `${((index + 1) / pages.length) * 100}%`; $('#bar').setAttribute('aria-valuenow', index + 1); $('#bar').setAttribute('aria-valuemax', pages.length);
  $('#prev').disabled = index === 0; $('#next').disabled = index === pages.length - 1;
  LB.reset(); LB.load(structuredClone(rec.scene));
  if (stage) stage.load();
  history.replaceState(null, '', `?book=${BOOK}&page=${index + 1}${q.get('mode') ? '&mode=' + q.get('mode') : ''}`);
  $('#end').hidden = index !== pages.length - 1;
  $('#how').href = `watch.html?book=${BOOK}&page=${index + 1}`;
  start = performance.now(); frames = 0;
  requestAnimationFrame(() => { canvasBox.classList.remove('turning'); text.classList.remove('turning'); updateMore(); });
  [index + 1, index - 1].filter(k => k >= 0 && k < pages.length).forEach(getPage);
}

function loop(now) {
  requestAnimationFrame(loop);
  if (!pages.length || (LITE && now - last < 31)) return;
  last = now;
  const t = ((now - start) / 1000) % LB.duration();
  if (stage) {
    cx += (tx * 1.5 - cx) * 0.12; cy += (ty * 0.7 - cy) * 0.12;
    stage.show(t, cx, cy);
    // Fall back to flat pages when this device cannot keep up: measured after start-up settles.
    if (++frames === 120 && !q.get('mode')) { const avg = (now - start) / frames; window.lastAvg = avg; if (avg > (LITE ? 50 : 40)) { useFlat(); show(index); } }
  } else if (flat) LB.render(flat.ctx, t, { scale: flat.s });
}

function bind() {
  $('#prev').onclick = () => show(index - 1);
  $('#next').onclick = () => show(index + 1);
  addEventListener('keydown', e => { if (e.key === 'ArrowRight') show(index + 1); if (e.key === 'ArrowLeft') show(index - 1); });
  let p0 = null;
  addEventListener('pointerdown', e => { p0 = [e.clientX, e.clientY]; });
  addEventListener('pointerup', e => {
    if (!p0) return; const dx = e.clientX - p0[0], dy = e.clientY - p0[1]; p0 = null;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) show(index + (dx < 0 ? 1 : -1));
  });
  canvasBox.addEventListener('pointermove', e => { if (e.pointerType !== 'mouse') return; const r = canvasBox.getBoundingClientRect(); tx = ((e.clientX - r.left) / r.width - 0.5) * 2; ty = -((e.clientY - r.top) / r.height - 0.5) * 2; });
  canvasBox.addEventListener('pointerleave', () => { tx = ty = 0; });
  addEventListener('deviceorientation', e => { if (e.gamma != null) { tx = Math.max(-1, Math.min(1, e.gamma / 25)); ty = Math.max(-1, Math.min(1, (45 - e.beta) / 25)); } });
  addEventListener('resize', () => stage?.resize());
  text.addEventListener('scroll', updateMore, { passive: true });
}

function hint() {
  if (index !== 0) return;
  const h = document.createElement('div'); h.id = 'hint';
  h.textContent = matchMedia('(pointer: coarse)').matches ? 'Swipe to turn the page · tilt to look around' : 'Use the arrow keys to turn · move the mouse to look around';
  canvasBox.append(h); setTimeout(() => { h.style.opacity = 0; setTimeout(() => h.remove(), 700); }, 3200);
}

async function main() {
  const book = await (await fetch(`data/${BOOK}/book.json`)).json();
  pages = book.pages; title.textContent = book.title; document.title = `${book.title} · Living Books`;
  if (book.game) { const g = $('#play'); g.href = book.game; g.hidden = false; }
  bind();
  if (mode === 'popup') useStage(); else useFlat();
  await show((+q.get('page') || 1) - 1);
  hint();
  requestAnimationFrame(loop);
  window.reader = { show, get mode() { return mode; } };
}
main();

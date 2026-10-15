import { get, post } from './api.js';
import { displayTitle, state } from './state.js';

const LS_KEY = 'ky_review_run';
const today = () => new Date().toISOString().slice(0, 10);

let session = null;          // {items, i, counts:{good,hard,again}, scope}
let revealed = false;

function saveRun() {
  if (!session) return;
  localStorage.setItem(LS_KEY, JSON.stringify({ at: today(), ...session }));
}

function loadRun() {
  try {
    const s = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
    if (s && s.at === today() && s.items && s.i < s.items.length) return s;
  } catch (e) { /* 忽略坏数据 */ }
  return null;
}

const clearRun = () => localStorage.removeItem(LS_KEY);

const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** 进入复习：优先恢复今天的会话；scope 不同或没有则拉取新队列。 */
export async function start(pointId = null) {
  const scope = pointId || null;
  const saved = loadRun();
  if (saved && (saved.scope || null) === scope) {
    session = { items: saved.items, i: saved.i, counts: saved.counts, scope: saved.scope };
  } else {
    const url = scope ? `/api/review/queue?point=${encodeURIComponent(scope)}` : '/api/review/queue';
    const q = await get(url).catch(() => null);
    session = { items: (q && q.items) || [], i: 0, counts: { good: 0, hard: 0, again: 0 }, scope };
  }
  revealed = false;
  saveRun();
  window.kyGo('review');
}

export function renderReview() {
  if (!session) {
    const saved = loadRun();
    if (saved) { renderResume(saved); return; }
    start();                                   // 直接进入全量队列
    return;
  }
  paint();
}

function renderResume(saved) {
  const box = document.getElementById('s-review');
  box.innerHTML = `<div class="card"><h3>继续上次复习</h3>
    <p class="small">进度 ${saved.i}/${saved.items.length} · 已评 ${saved.i} 条</p>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn sm" onclick="window.kyReview.resume()">继续</button>
      <button class="btn sm ghost" onclick="window.kyReview.restart()">重新拉取队列</button>
    </div></div>`;
}

function intervalLabel(n) {
  return n == null ? '毕业' : (n === 1 ? '1 天' : `${n} 天`);
}

function paint() {
  const box = document.getElementById('s-review');
  if (session.i >= session.items.length) { paintDone(box); return; }
  const it = session.items[session.i];
  const hit = state.pointIndex.get(it.point_id);
  const p = hit && hit.point;
  const units = (p && p.units) || [];
  const unitText = units[it.idx] || (p ? p.text : it.point_id);
  const crumb = hit ? `${hit.subj.name.slice(0, 8)} · ${hit.chap.name.slice(0, 14)}` : it.point_id;
  const pos = `${displayTitle(p)} · 第 ${it.idx + 1}/${units.length || '?'} 条`;
  const nxt = it.next || {};
  const left = session.items.length - session.i;
  box.innerHTML = `<div class="card rev-card">
    <div class="rev-top">
      <div><div class="rev-crumb">${crumb}</div><div class="rev-crumb2">${pos}</div></div>
      <button class="rev-exit" onclick="window.kyReview.exit()">先退出</button>
    </div>
    <div class="rev-text masked" id="rev-text">${esc(unitText.slice(0, 12))}……</div>
    <div class="rev-tip" id="rev-tip">先在心里回忆完整内容，再显示原文</div>
    <div class="rev-reveal"><button class="btn" style="width:100%" id="rev-btn" onclick="window.kyReview.reveal()">显示原文</button></div>
    <div class="rev-rate hidden" id="rev-rate">
      <button class="again" data-r="again" onclick="window.kyReview.rate('again')">忘了<small>${intervalLabel(nxt.again)}</small></button>
      <button class="hard" data-r="hard" onclick="window.kyReview.rate('hard')">吃力<small>${intervalLabel(nxt.hard)}</small></button>
      <button class="good" data-r="good" onclick="window.kyReview.rate('good')">秒答<small>${intervalLabel(nxt.good)}</small></button>
    </div>
    <div class="rev-foot"><span class="small">本次剩 ${left} 条</span>
      <button class="btn sm ghost" onclick="window.kyReview.skip()">跳过</button></div>
  </div>`;
  revealed = false;
}

function paintDone(box) {
  const c = session.counts;
  const n = c.good + c.hard + c.again;
  if (!n && !session.items.length) {
    box.innerHTML = `<div class="card" style="text-align:center">
      <h3 style="justify-content:center">今天没有到期的复习 ✓</h3>
      <p class="small">去「看」页学新考点；标记过的单元会按间隔回到这里。</p>
      <button class="btn" onclick="window.kyGo('look')">去看页</button></div>`;
  } else {
    box.innerHTML = `<div class="card" style="text-align:center">
      <h3 style="justify-content:center">本次复习完成 🎉</h3>
      <p>共评 ${n} 条：秒答 ${c.good} · 吃力 ${c.hard} · 忘了 ${c.again}</p>
      <p class="small">没清完的到期条目会留在队列里，下次继续。</p>
      <button class="btn" onclick="window.kyGo('today')">回今日</button></div>`;
  }
  session = null;
  clearRun();
}

const current = () => (session && session.i < session.items.length ? session.items[session.i] : null);

function reveal() {
  if (!current()) return;
  revealed = true;
  const hit = state.pointIndex.get(current().point_id);
  const p = hit && hit.point;
  const text = ((p && p.units) || [])[current().idx] || (p ? p.text : current().point_id);
  const el = document.getElementById('rev-text');
  el.textContent = text;
  el.classList.remove('masked');
  document.getElementById('rev-btn').parentElement.classList.add('hidden');
  document.getElementById('rev-rate').classList.remove('hidden');
  document.getElementById('rev-tip').textContent = '如实评分：忘了 = 完全想不起';
}

function next() {
  session.i += 1;
  saveRun();
  paint();
  window.scrollTo({ top: 0 });
}

async function rate(rating) {
  const it = current();
  if (!it) return;
  session.counts[rating] = (session.counts[rating] || 0) + 1;
  next();
  await post('/api/unit_review', { point_id: it.point_id, idx: it.idx, rating }).catch(() => {});
}

export const kyReview = {
  start: (pid) => start(pid || null),
  renderReview,
  reveal,
  rate,
  skip: next,
  exit() { saveRun(); window.kyGo('today'); },
  resume() {
    const s = loadRun();
    if (!s) { session = null; start(); return; }
    session = { items: s.items, i: s.i, counts: s.counts, scope: s.scope };
    revealed = false;
    paint();
  },
  restart() { clearRun(); session = null; start(); },
};
window.kyReview = kyReview;

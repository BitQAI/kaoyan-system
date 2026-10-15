import { get, post } from './api.js';
import { displayTitle, state } from './state.js';

const LS_KEY = 'ky_review_run';
const today = () => new Date().toISOString().slice(0, 10);
const QUICKS = [
  { k: 'due', label: '今日到期' },
  { k: 'today_look', label: '今日看点' },
  { k: 'fav', label: '收藏' },
  { k: 'hot', label: '易错·高频' },
];
const FILTERS = [
  { k: 'due', label: '待复习' },
  { k: 'fav', label: '收藏' },
  { k: 'weak', label: '没学完' },
  { k: 'hot', label: '易错·高频' },
];

let session = null;      // {items, i, counts, scope, label}
let flipped = false;
let scope = { quick: 'due', chapters: new Set(), points: new Set(), filters: new Set() };
let expandedSubj = new Set();
let countTimer = null;

const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ---------- 会话持久化（兼容 V3 旧数据：无 kind 视为 unit） ----------

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

// ---------- 落地：范围面板 ----------

export function renderMemo() {
  if (session) { paint(); return; }
  renderScope();
}

function scopeLabel() {
  if (scope.chapters.size || scope.points.size) {
    const parts = [];
    if (scope.chapters.size) parts.push(`${scope.chapters.size} 章`);
    if (scope.points.size) parts.push(`${scope.points.size} 点`);
    return `自定义（${parts.join(' · ')}）`;
  }
  const q = QUICKS.find((x) => x.k === scope.quick);
  return q ? q.label : '今日到期';
}

function buildParams() {
  const p = { quick: (scope.chapters.size || scope.points.size) ? 'due' : (scope.quick || 'due') };
  if (scope.chapters.size) p.chapters = [...scope.chapters].join(',');
  if (scope.points.size) p.points = [...scope.points].join(',');
  if (scope.filters.size) p.filter = [...scope.filters].join(',');
  return p;
}

function renderScope() {
  const box = document.getElementById('s-memo');
  const saved = loadRun();
  box.innerHTML = `
    ${saved ? `<div class="card"><h3>继续上次复习 <span class="small">${saved.i}/${saved.items.length}</span></h3>
      <div style="display:flex;gap:8px;margin-top:6px">
        <button class="btn sm" onclick="window.kyMemo.resumeRun()">继续</button>
        <button class="btn sm ghost" onclick="window.kyMemo.discardRun()">放弃，重新选择范围</button>
      </div></div>` : ''}
    <div class="card">
      <h3>开始复习 <span class="small" id="scope-mode"></span></h3>
      <div class="scope-sec"><b>快捷</b>
        <div class="schips">${QUICKS.map((q) =>
          `<button class="schip ${(!scope.chapters.size && !scope.points.size && scope.quick === q.k) ? 'on' : ''}"
            onclick="window.kyMemo.pickQuick('${q.k}')">${q.label}</button>`).join('')}</div>
      </div>
      <div class="scope-sec"><b>按科目 / 章节（可多选）</b>
        <div id="sc-chapters"></div>
      </div>
      <div class="scope-sec"><b>指定考点</b>
        <input class="blank-input" id="sc-pt-search" placeholder="输入关键词添加考点…"
          oninput="window.kyMemo.searchPoints(this.value)">
        <div id="sc-pt-results"></div>
        <div class="schips" id="sc-pt-selected" style="margin-top:6px"></div>
      </div>
      <div class="scope-sec"><b>筛选</b>
        <div class="schips">${FILTERS.map((f) =>
          `<button class="schip ${scope.filters.has(f.k) ? 'on' : ''}"
            onclick="window.kyMemo.toggleFilter('${f.k}')">${f.label}</button>`).join('')}</div>
      </div>
      <button class="btn" style="width:100%" id="sc-start" disabled
        onclick="window.kyMemo.start()">计算中…</button>
    </div>`;
  paintChapters();
  paintSelectedPoints();
  scheduleCount();
}

function paintChapters() {
  const wrap = document.getElementById('sc-chapters');
  wrap.innerHTML = state.content.subjects.filter((s) => (s.chapters || []).length).map((s) => {
    const chs = s.chapters;
    const all = chs.every((c) => scope.chapters.has(c.id));
    const any = chs.some((c) => scope.chapters.has(c.id));
    const open = expandedSubj.has(s.id) || any;
    return `<div class="chgroup">
      <div class="chkrow ch-head">
        <input type="checkbox" ${all ? 'checked' : ''}
          onchange="window.kyMemo.toggleSubject('${s.id}', this.checked)">
        <b style="flex:1">${s.name.slice(0, 10)}</b>
        <span class="small">${chs.length} 章</span>
        <button class="rev-exit" onclick="window.kyMemo.expandSubj('${s.id}')">${open ? '▴' : '▾'}</button>
      </div>
      ${open ? chs.map((c) => `<div class="chkrow" style="padding-left:24px">
        <input type="checkbox" ${scope.chapters.has(c.id) ? 'checked' : ''}
          onchange="window.kyMemo.toggleChapter('${c.id}', this.checked)">
        <span style="flex:1">${c.name.slice(0, 16)}</span>
        <span class="small">${c.weight_center || 0} 分</span></div>`).join('') : ''}
    </div>`;
  }).join('');
}

function paintSelectedPoints() {
  const el = document.getElementById('sc-pt-selected');
  if (!el) return;
  el.innerHTML = [...scope.points].map((pid) => {
    const hit = state.pointIndex.get(pid);
    return `<button class="schip on" onclick="window.kyMemo.removePoint('${pid}')"
      >${esc(displayTitle(hit && hit.point).slice(0, 16))} ×</button>`;
  }).join('');
}

function clearExplicit() {
  scope.chapters.clear();
  scope.points.clear();
}

function scheduleCount() {
  clearTimeout(countTimer);
  const btn = document.getElementById('sc-start');
  if (btn) { btn.disabled = true; btn.textContent = '计算中…'; }
  countTimer = setTimeout(async () => {
    const q = await get('/api/memo/queue?' + new URLSearchParams(buildParams())).catch(() => null);
    const el = document.getElementById('sc-start');
    if (!el) return;
    const n = q ? q.total : 0;
    el.disabled = !n;
    el.textContent = n ? `开始复习（约 ${n} 张 · ${q.est_min} 分钟）` : '该范围暂无可复习内容';
  }, 350);
}

async function start() {
  const q = await get('/api/memo/queue?' + new URLSearchParams(buildParams())).catch(() => null);
  const items = (q && q.items) || [];
  if (!items.length) { scheduleCount(); return; }
  session = { items, i: 0, counts: { good: 0, hard: 0, again: 0 },
              scope: buildParams(), label: scopeLabel() };
  flipped = false;
  saveRun();
  paint();
}

// ---------- 会话：翻转卡 ----------

function intervalLabel(n) {
  return n == null ? '毕业' : (n === 1 ? '1 天' : `${n} 天`);
}

function cardById(cid) {
  for (const subj of state.content.subjects) {
    for (const ch of subj.chapters || []) {
      for (const c of ch.cards || []) if (c.id === cid) return c;
    }
  }
  return null;
}

function paint() {
  const box = document.getElementById('s-memo');
  if (session.i >= session.items.length) { paintDone(box); return; }
  const it = session.items[session.i];
  const kind = it.kind || 'unit';
  const hit = state.pointIndex.get(it.point_id);
  const p = hit && hit.point;
  const crumb = hit ? `${hit.subj.name.slice(0, 8)} · ${hit.chap.name.slice(0, 14)}` : (it.point_id || '');
  let front = '';
  let back = '';
  let pos = '';
  if (kind === 'card') {
    const cd = cardById(it.card_id) || { front: '（卡片缺失）', back: '' };
    pos = `${esc(displayTitle(p))} · 背题卡`;
    front = `<div class="small">${cd.kind ? `<span class="chip b">${cd.kind}</span>` : ''}背题卡</div>
      <b class="memo-q">${esc(cd.front)}</b>`;
    const ks = (p && p.keywords) || [];
    back = `${ks.length ? `<div class="anchors">${ks.map((k) => `<span class="chip b">${esc(k)}</span>`).join('')}</div>` : ''}
      <span class="small">答案（AI 生成，请对照教材）</span>
      <p class="memo-a">${esc(cd.back)}</p>`;
  } else {
    const units = (p && p.units) || [];
    const text = units[it.idx] || (p ? p.text : it.point_id);
    pos = `${esc(displayTitle(p))} · 第 ${it.idx + 1}/${units.length || '?'} 条`;
    front = `<div class="small">单元卡</div>
      <div class="memo-q">${esc(text.slice(0, 12))}……</div>`;
    back = `<span class="small">原文</span><p class="memo-a">${esc(text)}</p>`;
  }
  const nxt = it.next || {};
  const left = session.items.length - session.i;
  box.innerHTML = `<div class="card rev-card">
    <div class="rev-top">
      <div><div class="rev-crumb">${crumb} · ${esc(session.label || '')}</div>
        <div class="rev-crumb2">${pos}</div></div>
      <button class="rev-exit" onclick="window.kyMemo.exit()">先退出</button>
    </div>
    <div class="mflip" id="mflip" onclick="window.kyMemo.flip()">
      <div class="mflip-inner">
        <div class="mflip-face">${front}<span class="memo-hint">轻点卡片翻面</span></div>
        <div class="mflip-face back">${back}</div>
      </div>
    </div>
    <div class="rev-tip" id="memo-tip">先在心里回忆完整内容，再翻面核对</div>
    <div class="rev-rate hidden" id="rev-rate">
      <button class="again" onclick="window.kyMemo.rate('again')">忘了<small>${intervalLabel(nxt.again)}</small></button>
      <button class="hard" onclick="window.kyMemo.rate('hard')">吃力<small>${intervalLabel(nxt.hard)}</small></button>
      <button class="good" onclick="window.kyMemo.rate('good')">秒答<small>${intervalLabel(nxt.good)}</small></button>
    </div>
    <div class="rev-foot"><span class="small">本次剩 ${left} 条</span>
      <button class="btn sm ghost" onclick="window.kyMemo.skip()">跳过</button></div>
  </div>`;
  flipped = false;
  requestAnimationFrame(() => {                     // 按较高一面定卡高（上限 420px 内部滚动）
    const el = document.getElementById('mflip');
    if (!el) return;
    const faces = [...el.querySelectorAll('.mflip-face')];
    const h = Math.max(200, ...faces.map((f) => f.scrollHeight));
    el.style.setProperty('--flip-h', Math.min(h, 420) + 'px');
  });
}

function flip() {
  const el = document.getElementById('mflip');
  if (!el) return;
  flipped = !flipped;
  el.classList.toggle('on', flipped);
  document.getElementById('rev-rate').classList.toggle('hidden', !flipped);
  document.getElementById('memo-tip').textContent = flipped
    ? '如实评分：忘了 = 完全想不起'
    : '先在心里回忆完整内容，再翻面核对';
}

function paintDone(box) {
  const c = session.counts;
  const n = c.good + c.hard + c.again;
  const label = session.label || '';
  if (!n && !session.items.length) {
    box.innerHTML = `<div class="card" style="text-align:center">
      <h3 style="justify-content:center">今天没有到期的复习 ✓</h3>
      <p class="small">选一个范围（如某章）开始翻卡，或先去「看」学新考点。</p>
      <button class="btn" onclick="window.kyMemo.panel()">选择范围</button></div>`;
  } else {
    box.innerHTML = `<div class="card" style="text-align:center">
      <h3 style="justify-content:center">本次复习完成 🎉</h3>
      <p>${esc(label)} · 共评 ${n} 条：秒答 ${c.good} · 吃力 ${c.hard} · 忘了 ${c.again}</p>
      <p class="small">没清完的到期条目会留在队列里，下次继续。</p>
      <div style="display:flex;gap:8px;justify-content:center">
        <button class="btn" onclick="window.kyMemo.panel()">选择范围</button>
        <button class="btn ghost" onclick="window.kyGo('today')">回今日</button>
      </div></div>`;
  }
  session = null;
  clearRun();
}

const current = () => (session && session.i < session.items.length ? session.items[session.i] : null);

function next() {
  session.i += 1;
  saveRun();
  paint();
  window.scrollTo({ top: 0 });
}

async function rate(rating) {
  const it = current();
  if (!it) return;
  session.counts[rating] += 1;
  const kind = it.kind || 'unit';
  next();
  if (kind === 'card') {
    await post('/api/card_review', { card_id: it.card_id, rating }).catch(() => {});
  } else {
    await post('/api/unit_review', { point_id: it.point_id, idx: it.idx, rating }).catch(() => {});
  }
}

export const kyMemo = {
  renderMemo,
  start,
  flip,
  rate,
  skip: next,
  exit() { saveRun(); session = null; renderScope(); },
  panel() { renderScope(); },
  resumeRun() {
    const s = loadRun();
    if (!s) { renderScope(); return; }
    session = { items: s.items, i: s.i, counts: s.counts, scope: s.scope, label: s.label };
    flipped = false;
    paint();
  },
  discardRun() { clearRun(); renderScope(); },
  pickQuick(k) {
    scope.quick = k;
    clearExplicit();
    renderScope();
  },
  toggleSubject(sid, on) {
    const subj = state.content.subjects.find((s) => s.id === sid);
    for (const c of (subj && subj.chapters) || []) {
      if (on) scope.chapters.add(c.id); else scope.chapters.delete(c.id);
    }
    scope.quick = 'due';
    expandedSubj.add(sid);
    renderScope();
  },
  toggleChapter(cid, on) {
    if (on) scope.chapters.add(cid); else scope.chapters.delete(cid);
    scope.quick = 'due';
    renderScope();
  },
  expandSubj(sid) {
    if (expandedSubj.has(sid)) expandedSubj.delete(sid); else expandedSubj.add(sid);
    renderScope();
  },
  searchPoints(q) {
    const box = document.getElementById('sc-pt-results');
    q = (q || '').trim();
    if (q.length < 2) { box.innerHTML = ''; return; }
    const hits = [];
    outer:
    for (const subj of state.content.subjects) {
      for (const ch of subj.chapters || []) {
        for (const p of ch.points || []) {
          if (p.text.includes(q) && !scope.points.has(p.id)) hits.push(p);
          if (hits.length >= 6) break outer;
        }
      }
    }
    box.innerHTML = hits.length ? hits.map((p) => `<div class="chkrow"
      onclick="window.kyMemo.addPoint('${p.id}')">
      <span style="flex:1">${esc(displayTitle(p).slice(0, 24))}</span>
      <span class="small">＋ 加入</span></div>`).join('')
      : '<p class="small">没有命中</p>';
  },
  addPoint(pid) { scope.points.add(pid); renderScope(); },
  removePoint(pid) { scope.points.delete(pid); renderScope(); },
  toggleFilter(k) {
    if (scope.filters.has(k)) scope.filters.delete(k); else scope.filters.add(k);
    renderScope();
  },
};
window.kyMemo = kyMemo;

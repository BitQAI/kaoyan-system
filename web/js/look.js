import { get, post } from './api.js';
import { state } from './state.js';

const TIER = { 1: '第一梯队', 2: '第二梯队', 3: '第三梯队' };
const CYCLE = [
  { s: 'new', label: '未', cls: '' },
  { s: 'known', label: '会', cls: 'g' },
  { s: 'half', label: '半', cls: 'o' },
  { s: 'review', label: '不会', cls: 'r' },
];
let subject = '812';
let favorites = new Set();

export async function renderLook() {
  if (!state.states) {
    const d = await get('/api/progress').catch(() => ({ states: {}, reports: [] }));
    state.states = d.states || {};
    state.reports = d.reports || [];
  }
  if (!state.favoritesLoaded) {
    const f = await get('/api/favorites').catch(() => ({}));
    favorites = new Set(f.point || []);
    state.favoritesLoaded = true;
  }
  paintSeg();
  paintChapters();
  document.getElementById('look-detail').classList.add('hidden');
  document.getElementById('look-chapters').classList.remove('hidden');
}

function paintSeg() {
  document.getElementById('look-seg').innerHTML = state.content.subjects.map((s) => {
    const dis = s.has_content === false;
    return `<button class="${s.id === subject ? 'on' : ''}" ${dis ? 'disabled' : ''}
      onclick="window.kyLook.subject('${s.id}')">${s.name.slice(0, 9)}${dis ? '·看板' : ''}</button>`;
  }).join('');
}

function chapterCompletion(chapId) {
  const rep = (state.reports || []).find((r) => r.id === subject);
  const hit = rep && (rep.chapters || []).find((c) => c.id === chapId);
  return hit ? hit.completion : 0;
}

function paintChapters() {
  const subj = state.content.subjects.find((s) => s.id === subject);
  if (!subj || !(subj.chapters || []).length) {
    document.getElementById('look-chapters').innerHTML =
      '<div class="card"><div class="empty">该科暂无内容（仅进度看板）。</div></div>';
    return;
  }
  document.getElementById('look-chapters').innerHTML = subj.chapters.map((ch) => `
    <div class="card" style="cursor:pointer" onclick="window.kyLook.open('${ch.id}')">
      <h3>${ch.name}
        <span class="badge t${ch.tier || 3}">${TIER[ch.tier] || '第三梯队'} · ${ch.weight_center || 0} 分</span></h3>
      <div class="bar"><i style="width:${Math.round(chapterCompletion(ch.id) * 100)}%"></i></div>
    </div>`).join('');
}

function mediaHtml(media) {
  return (media || []).map((m) => {
    if (m.type === 'formula' && m.tex) {
      return `<div class="media"><div class="tex" data-tex="${m.tex.replace(/"/g, '&quot;')}"></div>
        <div class="figcap">${m.caption || ''}</div></div>`;
    }
    if (m.src) {
      return `<div class="media"><img loading="lazy" src="/${m.src}" alt="${m.caption || ''}">
        <div class="figcap">${m.caption || ''}${m.source ? ' · 来源：' + m.source : ''}${m.license ? '（' + m.license + '）' : ''}</div></div>`;
    }
    return '';
  }).join('');
}

function pointHtml(p) {
  const st = (state.states[p.id] || 'new');
  const cur = CYCLE.find((c) => c.s === st) || CYCLE[0];
  const tags = (p.tags || []).map((t) =>
    `<span class="chip ${t === '易错' ? 'r' : t === '重点' ? 'o' : ''}">${t}</span>`).join('');
  const fav = favorites.has(p.id) ? 'on' : '';
  return `<div class="pcard">
    <div class="row">
      <div class="t"><b>${p.text.slice(0, 34)}</b><span class="small">${tags}</span></div>
      <button class="chip ${cur.cls}" onclick="window.kyLook.cycle('${p.id}', this)">${cur.label}</button>
      <button class="star ${fav}" onclick="window.kyLook.star('${p.id}', this)">★</button>
    </div>
    ${mediaHtml(p.media)}
    <p class="ptext">${p.text}</p>
    <button class="btn sm ghost" onclick="window.kyAI && window.kyAI.open('point','${p.id}')">问 AI</button>
  </div>`;
}

function renderTex(root) {
  if (!window.katex) return;
  root.querySelectorAll('.tex[data-tex]').forEach((el) => {
    try { window.katex.render(el.dataset.tex, el, { throwOnError: false, displayMode: false }); }
    catch (e) { el.textContent = el.dataset.tex; }
  });
}

async function openChapter(chId) {
  const subj = state.content.subjects.find((s) => s.id === subject);
  const chap = subj.chapters.find((c) => c.id === chId);
  document.getElementById('look-chapters').classList.add('hidden');
  const view = document.getElementById('look-detail');
  view.classList.remove('hidden');
  view.innerHTML = `<button class="btn sm ghost" style="margin:0 0 10px" onclick="window.kyLook.back()">← 返回章节</button>
    <div class="card"><h3>${chap.name}
      <span class="badge t${chap.tier || 3}">${TIER[chap.tier] || ''} · ${chap.weight_center || 0} 分</span></h3>
      ${(chap.points || []).map(pointHtml).join('') || '<div class="empty">暂无考点</div>'}</div>`;
  renderTex(view);
}

async function cycleState(pid, btn) {
  const cur = state.states[pid] || 'new';
  const i = CYCLE.findIndex((c) => c.s === cur);
  const next = CYCLE[(i + 1) % CYCLE.length];
  state.states[pid] = next.s;
  btn.className = 'chip ' + next.cls;
  btn.textContent = next.label;
  await post('/api/progress', { point_id: pid, state: next.s }).catch(() => {});
  const rep = (state.reports || []).find((r) => r.id === subject);
  if (rep) {
    const chap = state.content.subjects.find((s) => s.id === subject).chapters
      .find((c) => (c.points || []).some((p) => p.id === pid));
    if (chap) {
      const hit = (rep.chapters || []).find((c) => c.id === chap.id);
      if (hit) {
        const pts = chap.points || [];
        const coef = { known: 1, review: 0.6, half: 0.5, listened: 0.3, new: 0 };
        hit.completion = pts.reduce((acc, p) => acc + (coef[state.states[p.id] || 'new'] || 0), 0) / (pts.length || 1);
      }
    }
  }
}

async function starPoint(pid, btn) {
  const on = favorites.has(pid);
  if (on) { favorites.delete(pid); btn.classList.remove('on'); } else { favorites.add(pid); btn.classList.add('on'); }
  await post('/api/favorite', { type: 'point', ref_id: pid, action: on ? 'remove' : 'add' }).catch(() => {});
}

export const kyLook = {
  subject(s) { subject = s; renderLook(); },
  open: openChapter,
  back: renderLook,
  cycle: cycleState,
  star: starPoint,
  _subject: () => subject,
};
window.kyLook = kyLook;

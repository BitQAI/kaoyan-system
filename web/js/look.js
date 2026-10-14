import { get, post } from './api.js';
import { state, tagClass } from './state.js';

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
  state.dueSet = new Set((await get('/api/reviews/due').catch(() => ({ items: [] }))).items
    .map((x) => x.point_id));
  paintSeg();
  paintChapters();
  document.getElementById('look-search').value = '';
  document.getElementById('look-detail').classList.add('hidden');
  document.getElementById('look-chapters').classList.remove('hidden');
}

/** 跳转到某考点：切科目 → 开章节 → 滚动高亮。 */
export async function jumpTo(pointId) {
  const hit = state.pointIndex.get(pointId);
  if (!hit) return;
  if (hit.subj.has_content === false) return;
  subject = hit.subj.id;
  await renderLook();
  await openChapter(hit.chap.id);
  const el = document.getElementById('pt-' + pointId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('highlight');
    setTimeout(() => el.classList.remove('highlight'), 2600);
  }
}

function search(q) {
  const box = document.getElementById('look-chapters');
  const detail = document.getElementById('look-detail');
  q = (q || '').trim();
  if (q.length < 2) {
    renderLook();
    return;
  }
  detail.classList.add('hidden');
  box.classList.remove('hidden');
  const results = [];
  for (const subj of state.content.subjects) {
    for (const ch of subj.chapters || []) {
      for (const p of ch.points || []) {
        if (p.text.includes(q)) results.push({ subj, ch, p });
        if (results.length >= 40) break;
      }
    }
  }
  const hl = (t) => t.replace(q, `<mark>${q}</mark>`);
  box.innerHTML = results.length ? results.map(({ subj, ch, p }) => `
    <div class="card" style="cursor:pointer;padding:10px 12px" onclick="window.kyLook.jumpTo('${p.id}')">
      <div class="small">${subj.name.slice(0, 8)} · ${ch.name.slice(0, 14)}</div>
      <div style="font-size:13.5px">${hl(p.text.slice(0, 60))}</div>
    </div>`).join('') : '<div class="card"><div class="empty">没有命中（换关键词试试）</div></div>';
}

function paintSeg() {
  document.getElementById('look-seg').innerHTML = state.content.subjects.map((s) => {
    const dis = s.has_content === false;
    return `<button class="${s.id === subject ? 'on' : ''}"
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
    document.getElementById('look-chapters').innerHTML = `<div class="card">
      <h3>${subj ? subj.name : subject} <span class="badge t3">内容规划中</span></h3>
      <p class="ptext muted">本科目尚未录制考点与解析。英语（二）以真题精读和词汇积累为主，
      可先点下方按钮直接向 AI 提问（如作文模板、长难句分析）。</p>
      <button class="btn sm" onclick="window.kyAI && window.kyAI.open('free')">问 AI</button>
    </div>`;
    return;
  }
  document.getElementById('look-chapters').innerHTML = subj.chapters.map((ch) => {
    const hasAudio = (ch.listen || []).length || (ch.points || []).some((p) => (p.audio || []).length);
    const off = window.kyOffline && window.kyOffline.status(ch.id);
    return `
    <div class="card" style="cursor:pointer" onclick="window.kyLook.open('${ch.id}')">
      <h3>${ch.name}
        <span class="badge t${ch.tier || 3}">${TIER[ch.tier] || '第三梯队'} · ${ch.weight_center || 0} 分</span></h3>
      <div class="bar"><i style="width:${Math.round(chapterCompletion(ch.id) * 100)}%"></i></div>
      ${hasAudio ? `<div style="margin-top:8px">
        <button class="btn sm ghost" onclick="event.stopPropagation(); window.kyOffline.downloadFromCard('${ch.id}', this)">${off ? '已离线 ✓' : '⇩ 下载本章音频'}</button>
      </div>` : ''}
    </div>`;
  }).join('');
}

function mediaHtml(media) {
  return (media || []).map((m) => {
    if (m.type === 'formula' && m.tex) {
      return `<div class="media"><div class="tex" data-tex="${m.tex.replace(/"/g, '&quot;')}"></div>
        <div class="figcap">${m.caption || ''}</div></div>`;
    }
    if (m.src) {
      const lazy = /\.(png|jpe?g|webp)$/i.test(m.src) ? 'lazy' : 'eager';   // SVG 极小且懒加载易漏载
      return `<div class="media"><img loading="${lazy}" src="/${m.src}" alt="${m.caption || ''}">
        <div class="figcap">${m.caption || ''}${m.source ? ' · 来源：' + m.source : ''}${m.license ? '（' + m.license + '）' : ''}</div></div>`;
    }
    return '';
  }).join('');
}

function pointHtml(p) {
  const st = (state.states[p.id] || 'new');
  const cur = CYCLE.find((c) => c.s === st) || CYCLE[0];
  const due = state.dueSet && state.dueSet.has(p.id)
    ? '<span class="chip r">待复习</span>' : '';
  const tags = due + (p.tags || []).map((t) =>
    `<span class="chip ${tagClass(t)}">${t}</span>`).join('');
  const fav = favorites.has(p.id) ? 'on' : '';
  const kws = (p.keywords || []).map((k) => `<span class="chip">${k}</span>`).join('');
  const body = p.note
    ? `<p class="ptext">${p.note}</p>`
    : '<p class="ptext muted">解析待生成 · 可先点「问 AI」讲解</p>';
  const exam = p.exam ? `<div class="exam"><b>考点怎么考</b>${p.exam}</div>` : '';
  return `<div class="pcard" id="pt-${p.id}">
    <div class="row">
      <div class="t"><b>${p.text.slice(0, 34)}</b><span class="small">${kws}${tags}</span></div>
      <button class="chip ${cur.cls}" onclick="window.kyLook.cycle('${p.id}', this)">${cur.label}</button>
      <button class="star ${fav}" onclick="window.kyLook.star('${p.id}', this)">★</button>
    </div>
    ${body}${exam}${mediaHtml(p.media)}
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
  jumpTo,
  search,
  _subject: () => subject,
};
window.kyLook = kyLook;

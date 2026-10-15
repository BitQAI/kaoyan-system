import { get, post } from './api.js';
import { displayTitle, state, tagClass } from './state.js';

const TIER = { 1: '第一梯队', 2: '第二梯队', 3: '第三梯队' };
const CYCLE = [
  { s: 'new', label: '○ 未', cls: '' },
  { s: 'known', label: '✓ 会', cls: 'g' },
  { s: 'half', label: '~ 半', cls: 'o' },
  { s: 'review', label: '✗ 不会', cls: 'r' },
];
const UNITS_SHOWN = 7;
let subject = '812';
let favorites = new Set();

export async function renderLook() {
  if (!state.states) {
    const d = await get('/api/progress').catch(() => ({ states: {}, reports: [] }));
    state.states = d.states || {};
    state.unitStates = d.unit_states || {};
    state.reports = d.reports || [];
  }
  if (!state.favoritesLoaded) {
    const f = await get('/api/favorites').catch(() => ({}));
    favorites = new Set(f.point || []);
    state.favoritesLoaded = true;
  }
  state.dueSet = new Set((await get('/api/review/queue').catch(() => ({ items: [] }))).items
    .map((x) => x.point_id));
  paintSeg();
  paintChapters();
  document.getElementById('look-search').value = '';
  document.getElementById('look-detail').classList.add('hidden');
  document.getElementById('look-chapters').classList.remove('hidden');
}

/** 跳转到某考点：切科目 → 开章节 → 自动展开 → 滚动高亮。 */
export async function jumpTo(pointId) {
  const hit = state.pointIndex.get(pointId);
  if (!hit) return;
  if (hit.subj.has_content === false) return;
  subject = hit.subj.id;
  await renderLook();
  await openChapter(hit.chap.id);
  expandPoint(pointId);
  const el = document.getElementById('pt-' + pointId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('highlight');
    setTimeout(() => el.classList.remove('highlight'), 2600);
  }
}

function collapseOthers(exceptPid) {
  document.querySelectorAll('#look-detail .pbody').forEach((b) => {
    if (b.id === 'pb-' + exceptPid) return;
    b.classList.add('hidden');
    const c = document.getElementById('caret-' + b.id.slice(3));
    if (c) c.textContent = '▾';
  });
}

function togglePoint(pid) {
  const body = document.getElementById('pb-' + pid);
  if (!body) return;
  const collapsed = body.classList.toggle('hidden');
  if (!collapsed) collapseOthers(pid);          // 一次只展开一个考点
  const caret = document.getElementById('caret-' + pid);
  if (caret) caret.textContent = collapsed ? '▾' : '▴';
}

function expandPoint(pid) {
  const body = document.getElementById('pb-' + pid);
  if (body) body.classList.remove('hidden');
  collapseOthers(pid);
  const caret = document.getElementById('caret-' + pid);
  if (caret) caret.textContent = '▴';
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
  document.getElementById('look-chapters').innerHTML = `<div class="card clist">` +
    subj.chapters.map((ch) => {
      const hasAudio = (ch.listen || []).length || (ch.points || []).some((p) => (p.audio || []).length);
      const off = window.kyOffline && window.kyOffline.status(ch.id);
      const pct = Math.round(chapterCompletion(ch.id) * 100);
      const tier = Math.min(ch.tier || 3, 3);
      return `<div class="crow" onclick="window.kyLook.open('${ch.id}')"
          style="background:linear-gradient(90deg, var(--soft) ${pct}%, transparent ${pct}%)">
        <span class="dot d${tier}"></span>
        <span class="cname">${ch.name}</span>
        <span class="cscore t${tier}">${ch.weight_center || 0}分</span>
        <span class="cpct">${pct}%</span>
        ${hasAudio ? `<button class="ico${off ? ' ok' : ''}" title="下载本章音频"
          onclick="event.stopPropagation(); window.kyLook.downloadAsk('${ch.id}', this)">${off ? '✓' : '⇩'}</button>` : '<span class="ico"></span>'}
        <span class="caret">›</span>
      </div>`;
    }).join('') + '</div>';
}

/** 轻量确认弹窗（Promise<boolean>）。 */
function confirmBox(msg, okText = '确定') {
  return new Promise((resolve) => {
    const mask = document.createElement('div');
    mask.className = 'cmask';
    mask.innerHTML = `<div class="cbox"><p>${msg}</p>
      <div class="cbtns"><button class="btn sm ghost" data-x>取消</button>
      <button class="btn sm" data-ok>${okText}</button></div></div>`;
    document.body.appendChild(mask);
    const close = (v) => { mask.remove(); resolve(v); };
    mask.querySelector('[data-ok]').onclick = () => close(true);
    mask.querySelector('[data-x]').onclick = () => close(false);
    mask.onclick = (e) => { if (e.target === mask) close(false); };
  });
}

/** 点下载图标：先弹窗确认，再下载本章音频。 */
async function downloadAsk(chapId, btn) {
  const subj = state.content.subjects.find((s) => s.id === subject);
  const chap = subj && subj.chapters.find((c) => c.id === chapId);
  if (!chap) return;
  const n = (chap.listen || []).length + (chap.points || []).reduce((a, p) => a + (p.audio || []).length, 0);
  if (!n) { btn.textContent = '无音频'; return; }
  const ok = await confirmBox(`下载《${chap.name}》的 ${n} 段音频到本地？\n下载后无网络也能收听本章。`, '下载');
  if (!ok) return;
  const old = btn.textContent;
  btn.textContent = '…';
  const r = await window.kyOffline.download(chapId);
  btn.textContent = r.total && r.ok === r.total ? '✓' : '⇩';
  if (!(r.total && r.ok === r.total)) btn.textContent = old;
  btn.classList.toggle('ok', r.total > 0 && r.ok === r.total);
}

function mediaHtml(media) {
  return (media || []).map((m) => {
    if (m.type === 'formula' && m.tex) {
      return `<div class="media"><div class="tex" data-tex="${m.tex.replace(/"/g, '&quot;')}"></div>
        <div class="figcap">${m.caption || ''}</div></div>`;
    }
    if (m.src) {
      // 动态插入的懒加载图在滚动容器内可能永不触发，统一 eager（每章图片数量有限）
      return `<div class="media"><img loading="eager" src="/${m.src}" alt="${m.caption || ''}">
        <div class="figcap">${m.caption || ''}${m.source ? ' · 来源：' + m.source : ''}${m.license ? '（' + m.license + '）' : ''}</div></div>`;
    }
    return '';
  }).join('');
}

/** 考点分条：优先按分号切；无分号按句号切，最多 6 条。 */
function examBullets(exam) {
  let parts = (exam || '').split(/[；;]/).map((s) => s.trim()).filter(Boolean);
  if (parts.length <= 1) parts = (exam || '').split('。').map((s) => s.trim()).filter(Boolean);
  return parts.slice(0, 6);
}

function pointHtml(p) {
  const st = (state.states[p.id] || 'new');
  const cur = CYCLE.find((c) => c.s === st) || CYCLE[0];
  const fav = favorites.has(p.id) ? 'on' : '';
  // 徽标最多 3 个：待复习优先，其后关键词，再补标签
  const chips = [];
  if (state.dueSet && state.dueSet.has(p.id)) chips.push('<span class="chip r">待复习</span>');
  for (const k of (p.keywords || [])) { if (chips.length >= 3) break; chips.push(`<span class="chip">${k}</span>`); }
  for (const t of (p.tags || [])) {
    if (chips.length >= 3) break;
    if (t === '时政' || t === '高频') chips.push(`<span class="chip ${tagClass(t)}">${t}</span>`);
  }
  const hasBody = !!(p.note || p.exam || (p.media || []).length);
  return `<div class="prow" id="pt-${p.id}">
    <div class="prow-main" onclick="window.kyLook.toggle('${p.id}')">
      <div class="ptitle">${displayTitle(p)}</div>
      <div class="pmeta">${chips.join('')}</div>
    </div>
    <span class="chip ${cur.cls}" title="掌握程度（在「记」中复习评分）">${cur.label}</span>
    <button class="star ${fav}" onclick="event.stopPropagation(); window.kyLook.star('${p.id}', this)">★</button>
    <span class="caret" id="caret-${p.id}">${hasBody ? '▾' : ''}</span>
  </div>
  <div class="pbody hidden" id="pb-${p.id}">
    ${examBody(p)}
    ${mediaHtml(p.media)}
    ${noteBody(p)}
    <div class="pacts">
      <button class="btn sm ghost" onclick="event.stopPropagation(); window.kyQuiz && window.kyQuiz.startPoint ? window.kyQuiz.startPoint('${p.id}') : window.kyGo('test')">测这个考点</button>
      <button class="btn sm ghost" onclick="window.kyAI && window.kyAI.open('point','${p.id}')">问 AI</button>
    </div>
    <p class="small" style="margin:6px 0 0">${p.text}</p>
  </div>`;
}

function examBody(p) {
  if (!p.exam) return '';
  const items = examBullets(p.exam);
  return `<div class="exam"><b>考点怎么考</b><ul>${
    items.map((s) => `<li>${s}</li>`).join('')}</ul></div>`;
}

function unitItem(p, u, i) {
  const us = state.unitStates || {};
  const cur = CYCLE.find((c) => c.s === (us[`${p.id}#${i}`] || 'new')) || CYCLE[0];
  const more = i >= UNITS_SHOWN ? ` class="umore hidden" data-more="${p.id}"` : '';
  return `<li${more}><span class="utext">${u}</span>
    <span class="chip ustate ${cur.cls}" title="掌握程度（在「记」中复习评分）">${cur.label}</span></li>`;
}

function noteBody(p) {
  if (p.units && p.units.length) {
    const items = p.units.map((u, i) => unitItem(p, u, i)).join('');
    const more = p.units.length > UNITS_SHOWN
      ? `<button class="btn sm ghost umore-btn" onclick="event.stopPropagation(); window.kyLook.unitsMore('${p.id}', this)">展开剩余 ${p.units.length - UNITS_SHOWN} 条</button>`
      : '';
    const raw = p.note
      ? `<details class="notebox"><summary>查看完整原文</summary><p class="ptext">${p.note}</p></details>`
      : '';
    return `<div class="units"><b>理解要点 <span class="small">在「记」中复习评分</span></b>
      <ol>${items}</ol>${more}${raw}</div>`;
  }
  if (!p.note) return '';
  return `<details class="notebox"><summary>展开理解（${p.note.length} 字）</summary>
    <p class="ptext">${p.note}</p></details>`;
}

function unitsMore(pid, btn) {
  document.querySelectorAll(`[data-more="${pid}"]`).forEach((li) => li.classList.remove('hidden'));
  btn.remove();
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

async function starPoint(pid, btn) {
  const on = favorites.has(pid);
  if (on) { favorites.delete(pid); btn.classList.remove('on'); } else { favorites.add(pid); btn.classList.add('on'); }
  await post('/api/favorite', { type: 'point', ref_id: pid, action: on ? 'remove' : 'add' }).catch(() => {});
}

export const kyLook = {
  subject(s) { subject = s; renderLook(); },
  open: openChapter,
  back: renderLook,
  star: starPoint,
  downloadAsk,
  unitsMore,
  toggle: togglePoint,
  expand: expandPoint,
  jumpTo,
  search,
  _subject: () => subject,
};
window.kyLook = kyLook;

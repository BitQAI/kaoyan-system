import { get } from './api.js';
import { clipTitle, displayTitle, state } from './state.js';

const RING_COLORS = { 812: '#b33a3a', 315: '#b96a00', 101: '#2457d6', 204: '#11845b' };

export async function renderToday() {
  let data;
  try {
    data = await get('/api/plan/today');
  } catch (e) {
    document.getElementById('boot-error').style.display = 'block';
    document.getElementById('boot-error-msg').textContent = '计划加载失败（' + e.message + '）';
    return;
  }
  state.plan = data.plan;
  state.stats = await get('/api/stats').catch(() => null);
  document.getElementById('days').textContent = '距考试 ' + data.days_left + ' 天';

  const listen = document.getElementById('listen-list');
  const clips = data.plan.listen || [];
  document.getElementById('listen-meta').textContent =
    clips.length ? `碎片时间 · 约 ${data.plan.est_minutes} 分钟` : '';
  if (!clips.length) {
    listen.innerHTML = '<div class="empty">今日听单已清空（或内容未就绪）。</div>';
  } else {
    listen.innerHTML = clips.slice(0, 6).map((cid) => {
      const hit = state.clipIndex.get(cid);
      const dur = hit && hit.clip.dur ? Math.round(hit.clip.dur) + 's' : '';
      return `<div class="lrow" onclick="window.kyGo('listen')">
        <span class="dot d${hit ? Math.min(hit.chap.tier || 3, 3) : 3}"></span>
        <b class="lt">${clipTitle(cid)}</b>
        <span class="lsmall">${hit ? hit.chap.name.slice(0, 8) : ''}</span>
        <span class="lsmall">${dur}</span>
        <span class="caret">›</span></div>`;
    }).join('');
  }

  const tasks = document.getElementById('evening-tasks');
  const look = data.plan.look || [];
  const test = data.plan.test || [];
  tasks.innerHTML = `
    <div class="lrow" onclick="window.kyGo('look')">
      <span class="dot" style="background:var(--brand)"></span>
      <b class="lt">看：${look.length} 个考点</b>
      <span class="lsmall">${look.length ? displayTitle(state.pointIndex.get(look[0])?.point) : '暂无'}</span>
      <span class="caret">›</span></div>
    <div class="lrow" onclick="window.kyGo('test')">
      <span class="dot" style="background:var(--orange)"></span>
      <b class="lt">测：${test.length} 题</b>
      <span class="lsmall">含错题重练</span>
      <span class="caret">›</span></div>`;

  const reviewBox = document.getElementById('review-box');
  const due = data.review_units_due || 0;
  if (due > 0) {
    reviewBox.innerHTML = `<div class="card"><h3>今日复习 <span class="small">${due} 条到期 · 约 ${data.review_session_est_min || 0} 分钟</span></h3>
      <p class="small" style="margin:0 0 10px">先回忆、再看原文、如实评分；最不熟的先出，跨科交错。</p>
      <button class="btn" style="width:100%" onclick="window.kyGo('memo')">去「记」开始复习</button></div>`;
  } else {
    reviewBox.innerHTML = `<div class="card"><h3>今日复习 <span class="small">已完成 ✓</span></h3>
      <p class="small" style="margin:0">暂无到期条目。去「看」页学新考点，标记后会按间隔回来。</p></div>`;
  }

  const hour = new Date().getHours();
  const t = (state.stats && state.stats.today) || {};
  const doneTonight = (t.quiz_n || 0) + (t.cards || 0) + (t.review_n || 0) > 0;
  if (hour >= 21 && !doneTonight) {
    tasks.innerHTML += '<p class="small" style="margin:8px 0 0">睡前把今天的内容过一遍——睡一觉会帮你记得更牢。</p>';
  }

  const rings = document.getElementById('rings');
  if (state.stats && state.stats.ring) {
    rings.innerHTML = state.stats.ring.map((s) => {
      const pct = Math.round((s.weighted || 0) * 100);
      const c = RING_COLORS[s.id] || '#2457d6';
      return `<div><div class="ring" style="--p:${pct};--c:${c}"><i>${pct}%</i></div>
        <span class="small">${s.name.slice(0, 6)}</span></div>`;
    }).join('');
  }

  reorderCards(hour >= 18);
}

/** 时间自适应：白天听单优先，18 点后复习优先。 */
function reorderCards(evening) {
  const sec = document.getElementById('s-today');
  const order = evening
    ? ['review-box', 'card-tasks', 'card-listen', 'card-progress']
    : ['card-listen', 'card-tasks', 'review-box', 'card-progress'];
  for (const id of order) {
    const el = document.getElementById(id);
    if (el) sec.appendChild(el);
  }
}

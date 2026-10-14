import { get } from './api.js';
import { clipTitle, pointTitle, state, tagChips } from './state.js';

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
      const tier = hit && hit.chap.tier ? `t${hit.chap.tier}` : 't3';
      return `<div class="row"><span class="dot d${hit ? Math.min(hit.chap.tier || 3, 3) : 3}"></span>
        <div class="t"><b>${clipTitle(cid)}</b><span class="small">
        <span class="badge ${tier}">${hit ? hit.chap.name.slice(0, 10) : ''}</span>
        ${hit ? tagChips(hit.point, 2) : ''}
        ${hit && hit.clip.dur ? ' · ' + Math.round(hit.clip.dur) + 's' : ''}</span></div>
        <button class="btn sm" onclick="window.kyGo('listen')">听</button></div>`;
    }).join('');
  }

  const tasks = document.getElementById('evening-tasks');
  const look = data.plan.look || [];
  const test = data.plan.test || [];
  tasks.innerHTML = `
    <div class="row"><div class="t"><b>看：${look.length} 个考点卡</b>
      <span class="small">${look.slice(0, 2).map(pointTitle).join(' · ') || '暂无'}</span></div>
      <button class="btn sm ghost" onclick="window.kyGo('look')">去完成</button></div>
    <div class="row"><div class="t"><b>测：${test.length} 题</b>
      <span class="small">含错题重练</span></div>
      <button class="btn sm ghost" onclick="window.kyGo('test')">去完成</button></div>`;

  const reviewBox = document.getElementById('review-box');
  if (data.reviews_due > 0) {
    reviewBox.innerHTML = `<div class="card"><h3>今日复习 <span class="small">${data.reviews_due} 点到期</span></h3>` +
      (data.review_points || []).slice(0, 8).map((pid) => {
        const h = state.pointIndex.get(pid);
        return `<div class="row" style="cursor:pointer"
          onclick="window.kyGo('look'); setTimeout(function(){window.kyLook.jumpTo('${pid}')},350)">
          <div class="t"><b>${h ? h.point.text.slice(0, 26) : pid}</b>
            <span class="small">${h ? h.chap.name.slice(0, 12) : ''} · 标记「会」即推进复习</span></div>
          <span class="small">去复习 ›</span></div>`;
      }).join('') + '</div>';
  } else {
    reviewBox.innerHTML = '';
  }

  const rings = document.getElementById('rings');
  if (data.pace && data.pace.behind && data.pace.remaining_points > 0) {
    document.getElementById('streak-line').innerHTML =
      `连续打卡 <b style="color:var(--brand)">${state.stats ? state.stats.streak_days : 0}</b> 天 · ` +
      `待学 ${data.pace.remaining_points} 点 · 每天约 ${data.pace.per_day.toFixed(1)} 点可追平`;
  }
  if (state.stats && state.stats.ring) {
    rings.innerHTML = state.stats.ring.map((s) => {
      const pct = Math.round((s.weighted || 0) * 100);
      const c = RING_COLORS[s.id] || '#2457d6';
      return `<div><div class="ring" style="--p:${pct};--c:${c}"><i>${pct}%</i></div>
        <span class="small">${s.name.slice(0, 6)}</span></div>`;
    }).join('');
    if (!data.pace || !data.pace.behind) {
      document.getElementById('streak-line').innerHTML =
        `连续打卡 <b style="color:var(--brand)">${state.stats.streak_days}</b> 天 · ` +
        `昨日听 ${Math.round((state.stats.today.listen_sec || 0) / 60)} 分钟`;
    }
  }
}

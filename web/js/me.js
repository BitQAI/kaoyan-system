import { get, post } from './api.js';
import { shortTitle, state } from './state.js';

const RING_COLORS = { 812: '#b33a3a', 315: '#b96a00', 101: '#2457d6', 204: '#11845b' };

export async function renderMe() {
  const [stats, settings, threads, plan] = await Promise.all([
    get('/api/stats').catch(() => null),
    get('/api/settings').catch(() => ({})),
    get('/api/ai/threads').catch(() => ({ items: [] })),
    get('/api/plan/today').catch(() => null),
  ]);
  state.stats = stats || state.stats;

  const st = stats || {};
  const pace = plan && plan.pace;
  document.getElementById('me-streak').innerHTML = `
    <div class="row"><div class="t"><b>连续打卡</b>
      <span class="small">${st.streak_days || 0} 天 · 今日听 ${Math.round(((st.today || {}).listen_sec || 0) / 60)} 分钟</span></div></div>
    ${pace ? `<div class="row"><div class="t"><b>追赶节奏</b>
      <span class="small">待学 ${pace.remaining_points} 点 · 每天约 ${pace.per_day.toFixed(1)} 点可追平</span></div></div>` : ''}`;

  const ring = (stats && stats.ring) || [];
  document.getElementById('me-progress').innerHTML = ring.map((s) => {
    const pct = Math.round((s.weighted || 0) * 100);
    return `<div class="mrow" onclick="window.kyMe.gotoSubject('${s.id}')">
      <span class="dot" style="background:${RING_COLORS[s.id] || '#c3cbd8'}"></span>
      <b class="lt">${s.name}</b>
      <span class="minibar"><i style="width:${pct}%"></i></span>
      <span class="lsmall">${pct}%</span>
      <span class="caret">›</span></div>`;
  }).join('') || '<div class="empty">暂无数据</div>';

  const th = (threads.items || []);
  document.getElementById('me-threads').innerHTML = th.length ? th.map((t) => `
    <div class="lrow" onclick="window.kyMe.openThread('${t.id}','${t.owner_type}','${t.owner_ref || ''}')">
      <span class="dot" style="background:var(--brand2)"></span>
      <b class="lt">${shortTitle(t.title || t.owner_ref || '自由问答')}</b>
      <span class="lsmall">${t.owner_type === 'point' ? '知识点' : t.owner_type === 'quiz' ? '题目' : '自由'}</span>
      <span class="lsmall">${(t.updated_at || '').slice(5, 10)}</span>
      <span class="caret">›</span></div>`).join('') : '<div class="empty">还没有对话记录</div>';

  const voiceSel = ['Ethan', 'Cherry', 'Serena'].map((v) =>
    `<option ${settings.voice === v ? 'selected' : ''}>${v}</option>`).join('');
  document.getElementById('me-settings').innerHTML = `
    <div class="row"><div class="t"><b>每日听目标（分钟）</b></div>
      <input class="num" type="number" id="set-listen" value="${settings.listen_minutes || 40}" min="0" max="240"></div>
    <div class="row"><div class="t"><b>每日看点</b></div>
      <input class="num" type="number" id="set-look" value="${settings.look_n || 8}" min="0" max="50"></div>
    <div class="row"><div class="t"><b>每日测题</b></div>
      <input class="num" type="number" id="set-quiz" value="${settings.quiz_n || 15}" min="0" max="100"></div>
    <div class="row"><div class="t"><b>音色（下次生成音频生效）</b></div>
      <select id="set-voice">${voiceSel}</select></div>
    <button class="btn" style="margin-top:10px" onclick="window.kyMe.save()">保存设置</button>`;
  document.getElementById('me-export').innerHTML = `
    <div class="lrow" onclick="window.kyMe.exportFile('wrong')">
      <span class="dot" style="background:var(--red)"></span><b class="lt">错题清单</b>
      <span class="lsmall">题干/答案/解析</span><span class="ico">⇩</span></div>
    <div class="lrow" onclick="window.kyMe.exportFile('progress')">
      <span class="dot" style="background:var(--brand)"></span><b class="lt">备考进度表</b>
      <span class="lsmall">四科加权 + 各章进度</span><span class="ico">⇩</span></div>`;
  document.getElementById('me-pwd').innerHTML = `
    <div class="row"><div class="t"><b>修改密码</b><span class="small">写入 .env，重启服务后生效</span></div></div>
    <div class="row"><input class="num wide" type="password" id="pwd-old" placeholder="当前密码"></div>
    <div class="row"><input class="num wide" type="password" id="pwd-new" placeholder="新密码（≥6位）"></div>
    <button class="btn sm" onclick="window.kyMe.changePwd()">修改</button>
    <span class="small" id="pwd-msg" style="margin-left:10px"></span>`;
}

async function save() {
  await post('/api/settings', {
    listen_minutes: Number(document.getElementById('set-listen').value),
    look_n: Number(document.getElementById('set-look').value),
    quiz_n: Number(document.getElementById('set-quiz').value),
    voice: document.getElementById('set-voice').value,
  });
  alert('已保存');
}

async function changePwd() {
  const msg = document.getElementById('pwd-msg');
  try {
    await post('/api/settings/password', {
      old: document.getElementById('pwd-old').value,
      new: document.getElementById('pwd-new').value,
    });
    msg.textContent = '已修改，重启服务后生效';
  } catch (e) {
    msg.textContent = e.message === 'http_401' ? '旧密码不对' : '失败：' + e.message;
  }
}

function openThread(id, type, ref) {
  window.kyAI.open(type, ref || null);
}

async function exportFile(kind) {
  const r = await fetch('/api/export/' + kind, { credentials: 'same-origin' });
  if (!r.ok) return;
  const text = await r.text();
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const d = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  a.download = (kind === 'wrong' ? '错题清单-' : '备考进度-') + d + '.md';
  a.click();
  URL.revokeObjectURL(a.href);
}

/** 点进度行 → 切到该科的「看」页。 */
function gotoSubject(subjId) {
  if (window.kyGo) window.kyGo('look');
  if (window.kyLook) window.kyLook.subject(subjId);
}

export const kyMe = { save, changePwd, openThread, exportFile, gotoSubject };
window.kyMe = kyMe;

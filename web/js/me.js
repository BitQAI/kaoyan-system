import { get, post } from './api.js';
import { state } from './state.js';

export async function renderMe() {
  const [stats, settings, threads] = await Promise.all([
    get('/api/stats').catch(() => null),
    get('/api/settings').catch(() => ({})),
    get('/api/ai/threads').catch(() => ({ items: [] })),
  ]);
  state.stats = stats || state.stats;

  const ring = (stats && stats.ring) || [];
  document.getElementById('me-progress').innerHTML = ring.map((s) => `
    <div class="row"><div class="t"><b>${s.name}</b>
      <span class="small">加权 ${Math.round(s.weighted * 100)}% · 原始 ${Math.round(s.raw * 100)}%${
        s.has_content === false ? ' · 仅看板' : ''}</span></div>
      <div style="width:110px"><div class="bar"><i style="width:${Math.round(s.weighted * 100)}%"></i></div></div>
    </div>`).join('') || '<div class="empty">暂无数据</div>';

  const th = (threads.items || []);
  document.getElementById('me-threads').innerHTML = th.length ? th.map((t) => `
    <div class="row" style="cursor:pointer" onclick="window.kyMe.openThread('${t.id}','${t.owner_type}','${t.owner_ref || ''}')">
      <div class="t"><b>${t.title || t.owner_ref || '自由问答'}</b>
        <span class="small">${t.owner_type === 'point' ? '知识点' : t.owner_type === 'quiz' ? '题目' : '自由'} ·
        ${(t.updated_at || '').slice(0, 16).replace('T', ' ')}</span></div><span class="small">›</span>
    </div>`).join('') : '<div class="empty">还没有对话记录</div>';

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

export const kyMe = { save, changePwd, openThread };
window.kyMe = kyMe;

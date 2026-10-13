import { get, postStream } from './api.js';
import { state, pointTitle } from './state.js';

let ownerType = 'free';
let ownerRef = null;
let threadId = null;
let streaming = false;

const QUICK = ['讲简单点', '举个例子', '按考试答题格式给标准答案', '出 2 道相关的题', '我错在哪'];

export function openAI(type, ref) {
  ownerType = type || 'free';
  ownerRef = ref || null;
  threadId = null;
  const title = type === 'point' ? pointTitle(ref)
    : type === 'quiz' ? '题目追问'
    : '自由问答';
  document.getElementById('ai-title').textContent = '问 AI · ' + title;
  document.getElementById('ai-ctx').textContent =
    (type === 'point' ? '# ' + ref : type === 'quiz' ? '# ' + ref : '对话按知识点/题目归档');
  document.getElementById('mask').classList.add('on');
  document.getElementById('ai').classList.add('on');
  loadHistory();
}

function closeAI() {
  document.getElementById('mask').classList.remove('on');
  document.getElementById('ai').classList.remove('on');
}

async function loadHistory() {
  const chat = document.getElementById('chat');
  chat.innerHTML = '<div class="empty">围绕当前知识点提问；历史会保存在「我的」里。</div>';
  try {
    const threads = (await get('/api/ai/threads')).items || [];
    const hit = threads.find((t) => t.owner_type === ownerType &&
      (t.owner_ref || null) === (ownerRef || null));
    if (!hit) return;
    threadId = hit.id;
    const msgs = (await get(`/api/ai/threads/${hit.id}/messages`)).items || [];
    chat.innerHTML = '';
    for (const m of msgs) appendBubble(m.role, m.content, m.reasoning);
    chat.scrollTop = chat.scrollHeight;
  } catch (e) { /* 空历史 */ }
}

function appendBubble(role, content, reasoning) {
  const chat = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = 'bub ' + (role === 'user' ? 'u' : 'a');
  if (role === 'assistant' && reasoning) {
    div.innerHTML = `<details class="think"><summary>已深度思考 ▸</summary>${escapeHtml(reasoning)}</details>`;
  }
  div.appendChild(document.createTextNode(content || ''));
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br>');
}

async function ask(msg) {
  if (streaming) return;
  const text = (msg || '').trim();
  if (!text) return;
  streaming = true;
  appendBubble('user', text);
  const aiBub = appendBubble('assistant', '', '');
  let content = '';
  let reasoning = '';
  const think = document.createElement('details');
  think.className = 'think';
  think.innerHTML = '<summary>深度思考中…</summary>';
  think.style.display = 'block';
  aiBub.insertBefore(think, aiBub.firstChild);
  const body = document.createTextNode('');
  aiBub.appendChild(body);
  try {
    await postStream('/api/ai/chat',
      { owner_type: ownerType, owner_ref: ownerRef, message: text },
      (evt) => {
        if (evt.type === 'thread') threadId = evt.thread_id;
        else if (evt.type === 'reasoning') {
          reasoning += evt.delta;
          think.innerHTML = '<summary>已深度思考 ▸</summary>' + escapeHtml(reasoning);
        } else if (evt.type === 'content') {
          content += evt.delta;
          body.textContent = content;
        } else if (evt.type === 'error') {
          body.textContent = content + '\n（已中断，可重试' + (evt.partial_saved ? '；已保存部分内容' : '') + '）';
        }
        document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
      });
  } catch (e) {
    body.textContent = content + '（网络错误，可重试）';
  } finally {
    if (!content) think.remove();
    streaming = false;
  }
}

export const kyAI = { open: openAI, close: closeAI, ask };
window.kyAI = kyAI;

export function initAI() {
  document.getElementById('mask').addEventListener('click', closeAI);
  document.querySelectorAll('#ai-qchips button').forEach((b) =>
    b.addEventListener('click', () => ask(b.textContent)));
  const input = document.getElementById('ai-input');
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { ask(input.value); input.value = ''; } });
  document.getElementById('ai-send').addEventListener('click', () => { ask(input.value); input.value = ''; });
}

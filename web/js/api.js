export async function api(path, opts = {}) {
  const init = {
    method: opts.method || 'GET',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
  };
  if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
  const r = await fetch(path, init);
  if (r.status === 401) {
    window.dispatchEvent(new Event('ky-unauth'));
    throw new Error('unauthorized');
  }
  if (!r.ok) throw new Error('http_' + r.status);
  return r.json();
}

export const get = (p) => api(p);
export const post = (p, body) => api(p, { method: 'POST', body });

// ---------- 可靠提交：失败暂存本地，联网/下次成功时自动补发 ----------
const PENDING_KEY = 'ky_pending_posts';
const PENDING_MAX = 200;
let flushing = false;

function pendingList() {
  try { return JSON.parse(localStorage.getItem(PENDING_KEY) || '[]'); } catch (e) { return []; }
}

function pendingSave(list) {
  try {
    localStorage.setItem(PENDING_KEY, JSON.stringify(list.slice(-PENDING_MAX)));
  } catch (e) { /* localStorage 满则丢弃旧数据 */ }
}

const isBusinessError = (e) =>
  String(e && e.message).startsWith('http_4') || String(e && e.message) === 'unauthorized';

/** 关键写入（评分等）：网络失败入队稍后补发；业务错误（4xx/401）正常抛出。 */
export async function postReliable(path, body) {
  try {
    const r = await post(path, body);
    flushPending();                                   // 网络可用，顺手清积压
    return r;
  } catch (e) {
    if (isBusinessError(e)) throw e;
    const list = pendingList();
    list.push({ path, body, ts: Date.now() });
    pendingSave(list);
    return null;
  }
}

export async function flushPending() {
  if (flushing) return;
  const list = pendingList();
  if (!list.length) return;
  flushing = true;
  const rest = [];
  for (const item of list) {
    try {
      await post(item.path, item.body);
    } catch (e) {
      if (!isBusinessError(e)) rest.push(item);       // 仍离线 → 留队；4xx/401 → 丢弃
    }
  }
  pendingSave(rest);
  flushing = false;
}

window.addEventListener('online', () => flushPending());

/** SSE：逐事件回调。返回 promise，流结束 resolve。 */
export async function postStream(path, body, onEvent) {
  const r = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (r.status === 401) {
    window.dispatchEvent(new Event('ky-unauth'));
    throw new Error('unauthorized');
  }
  if (!r.ok || !r.body) throw new Error('http_' + r.status);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data:')) continue;
        try { onEvent(JSON.parse(line.slice(5).trim())); } catch (e) { /* 忽略坏帧 */ }
      }
    }
  }
}

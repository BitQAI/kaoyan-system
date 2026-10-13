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

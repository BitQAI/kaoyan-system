import { authHeaders } from "./api";

const RATE_KEY = "kaoyan.listen.rate";
export const RATE_MIN = 0.6;
export const RATE_MAX = 3.0;
export const RATE_DEFAULT = 1.5;

/** 语速：0.6–3.0，默认 1.5，跨会话记住 */
export function readRate(): number {
  try {
    const n = Number(localStorage.getItem(RATE_KEY));
    if (!Number.isFinite(n) || n <= 0) return RATE_DEFAULT;
    return Math.min(RATE_MAX, Math.max(RATE_MIN, n));
  } catch {
    return RATE_DEFAULT;
  }
}

export function writeRate(rate: number): void {
  try { localStorage.setItem(RATE_KEY, String(rate)); } catch { /* 隐私模式忽略 */ }
}

// 鉴权是 Bearer token，<audio src> 带不了 Authorization 头，只能 fetch 成 blob 再播
const urls = new Map<string, Promise<string>>();
const order: string[] = [];
let pinned = "";
const CACHE_MAX = 3;

function drop(cardId: string): void {
  const p = urls.get(cardId);
  if (!p) return;
  urls.delete(cardId);
  const i = order.indexOf(cardId);
  if (i >= 0) order.splice(i, 1);
  void p.then((url) => URL.revokeObjectURL(url)).catch(() => {});
}

/** 正在播放的一段不参与淘汰，避免边播边被回收 */
export function pinAudio(cardId: string): void {
  pinned = cardId;
}

export function loadAudio(cardId: string): Promise<string> {
  const hit = urls.get(cardId);
  if (hit) return hit;
  const task = fetch(`/api/audio/${cardId}`, { headers: authHeaders() })
    .then((res) => {
      if (!res.ok) throw new Error(`audio ${cardId} -> ${res.status}`);
      return res.blob();
    })
    .then((blob) => URL.createObjectURL(blob));
  urls.set(cardId, task);
  order.push(cardId);
  while (order.length > CACHE_MAX) {
    const victim = order.find((id) => id !== pinned);
    if (victim === undefined) break;
    drop(victim);
  }
  task.catch(() => drop(cardId));
  return task;
}

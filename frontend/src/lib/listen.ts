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

/** 词卡分片：同一个缓存与淘汰策略，key 用 `cardId:clip` */
export function loadClip(cardId: string, clip: string): Promise<string> {
  return loadAudio(cardId, clip);
}

export function loadAudio(cardId: string, clip?: string): Promise<string> {
  const key = clip ? `${cardId}:${clip}` : cardId;
  const hit = urls.get(key);
  if (hit) return hit;
  const url = clip ? `/api/audio/${cardId}?clip=${clip}` : `/api/audio/${cardId}`;
  const task = fetch(url, { headers: authHeaders() })
    .then((res) => {
      if (!res.ok) throw new Error(`audio ${key} -> ${res.status}`);
      return res.blob();
    })
    .then((blob) => URL.createObjectURL(blob));
  urls.set(key, task);
  order.push(key);
  while (order.length > CACHE_MAX) {
    const victim = order.find((id) => id !== pinned);
    if (victim === undefined) break;
    drop(victim);
  }
  task.catch(() => drop(key));
  return task;
}

/** 单段试听：不进入播放队列，点小喇叭重听单词/例句用；无音频时回退浏览器语音 */
let oncePlayer: HTMLAudioElement | null = null;

export function playClipOnce(cardId: string, clip: string | null,
                             text: string, lang = "en-US"): void {
  const speak = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      u.rate = Math.min(readRate(), 2);
      window.speechSynthesis.speak(u);
    } catch { /* 浏览器不支持就静默 */ }
  };
  const task = clip ? loadClip(cardId, clip) : loadAudio(cardId);
  task
    .then((url) => {
      oncePlayer?.pause();
      oncePlayer = oncePlayer ?? new Audio();
      oncePlayer.src = url;
      oncePlayer.playbackRate = readRate();
      oncePlayer.onerror = speak;
      void oncePlayer.play().catch(speak);
    })
    .catch(speak);
}

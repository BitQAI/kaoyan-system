import { get, post } from './api.js';
import { clipTitle, pointTitle, state } from './state.js';

const audio = new Audio();
audio.preload = 'metadata';

let queue = [];
let idx = -1;
let loopOne = false;
let rate = 1.0;
let saveTick = 0;
let posMap = {};          // clip_id -> {position_sec, plays}
let progressStates = {};  // point_id -> state

function fmt(s) {
  s = Math.max(0, Math.round(s || 0));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

function current() { return idx >= 0 && idx < queue.length ? queue[idx] : null; }

async function ensureMeta() {
  if (!Object.keys(posMap).length) {
    posMap = await get('/api/audio_pos').catch(() => ({}));
  }
  if (!Object.keys(progressStates).length) {
    progressStates = (await get('/api/progress').catch(() => ({ states: {} }))).states || {};
  }
}

export async function renderListen() {
  await ensureMeta();
  if (!queue.length) setQueue('plan');
  paintPlayer();
  paintQueue();
}

export function setQueue(mode) {
  cancelPrompt();
  ['plan', 'chapter', 'fav'].forEach((m) => {
    const b = document.getElementById('q-' + m);
    if (b) b.classList.toggle('on', m === mode);
  });
  if (mode === 'plan') {
    queue = (state.plan && state.plan.listen) || [];
  } else if (mode === 'chapter') {
    // 按权重章节顺序的全部音频（含已听）
    queue = [];
    for (const subj of state.content.subjects) {
      for (const chap of subj.chapters) {
        for (const p of chap.points) {
          for (const a of p.audio || []) {
            queue.push(a.src.replace(/^audio\//, '').replace(/\.mp3$/, ''));
          }
        }
      }
    }
  } else {
    queue = [];
  }
  idx = queue.length ? 0 : -1;
  paintQueue();
  paintPlayer();
}

export function playClip(cid) {
  cancelPrompt();
  const i = queue.indexOf(cid);
  if (i >= 0) idx = i;
  else { queue.unshift(cid); idx = 0; }
  loadAndPlay();
}

function loadAndPlay() {
  const cid = current();
  if (!cid) return;
  audio.src = '/audio/' + cid + '.mp3';
  const saved = posMap[cid] && posMap[cid].position_sec;
  if (saved && saved > 1) audio.currentTime = saved;
  audio.playbackRate = rate;
  audio.play().catch(() => {});
  // 预取下一段（弱网不断流）
  const nx = queue[idx + 1];
  if (nx) {
    const pre = new Audio();
    pre.preload = 'auto';
    pre.src = '/audio/' + nx + '.mp3';
  }
  paintPlayer();
  paintQueue();
  setupMediaSession(cid);
}

function onEnded() {
  const cid = current();
  if (loopOne) { audio.currentTime = 0; audio.play().catch(() => {}); return; }
  savePos(cid, true);
  markProgressIfDone(cid);
  const nx = queue[idx + 1];
  if (nx && shouldPrompt(cid, nx)) { showPrompt(cid, nx); return; }
  next();
}

/** 段间检索提示：跨考点（或串讲→考点）时插一段「先回忆」。 */
function shouldPrompt(prevCid, nextCid) {
  const a = state.clipIndex.get(prevCid);
  const b = state.clipIndex.get(nextCid);
  if (!a || !b || b.isChapter) return false;
  if (a.isChapter) return true;
  return a.point.id !== b.point.id;
}

let promptTimer = null;

function cancelPrompt() {
  if (promptTimer) { clearInterval(promptTimer); promptTimer = null; }
  const el = document.getElementById('p-prompt');
  if (el) el.classList.add('hidden');
}

function showPrompt(prevCid) {
  const el = document.getElementById('p-prompt');
  const hit = state.clipIndex.get(prevCid);
  const label = hit ? (hit.isChapter ? hit.chap.name + ' · 串讲' : hit.point.text.slice(0, 18)) : '';
  let sec = 8;
  const paint = () => {
    el.innerHTML = `<b>🎧 先回忆：刚才这段讲了哪几点？</b>
      <span class="small">刚听完：${label}</span>
      <div class="prompt-btns">
        <button class="btn sm" onclick="window.kyPlayer.promptGo()">继续 ▶（${sec}s）</button>
        <button class="btn sm ghost" onclick="window.kyPlayer.promptReplay('${prevCid}')">回听上段</button>
      </div>`;
  };
  el.classList.remove('hidden');
  paint();
  promptTimer = setInterval(() => { sec -= 1; if (sec <= 0) promptGo(); else paint(); }, 1000);
}

function next() {
  if (idx < queue.length - 1) { idx += 1; loadAndPlay(); }
  else { paintPlayer(); }
}

function prev() {
  if (audio.currentTime > 3) { audio.currentTime = 0; return; }
  if (idx > 0) { idx -= 1; loadAndPlay(); }
}

async function savePos(cid, countPlay) {
  if (!cid) return;
  posMap[cid] = { position_sec: audio.currentTime, plays: (posMap[cid] && posMap[cid].plays) || 0 };
  await post('/api/audio_pos', {
    clip_id: cid,
    position_sec: audio.currentTime,
    plays_delta: countPlay ? 1 : 0,
  }).catch(() => {});
}

async function markProgressIfDone(cid) {
  const hit = state.clipIndex.get(cid);
  if (!hit) return;
  let targets = [];
  if (hit.isChapter) {
    targets = hit.point_ids || [];                 // 整章串讲播完 → 全章点记为已听
  } else {
    const clips = hit.point.audio || [];
    const lastSrc = clips.length ? clips[clips.length - 1].src : '';
    const lastCid = lastSrc.replace(/^audio\//, '').replace(/\.mp3$/, '');
    if (cid === lastCid) targets = [hit.point.id]; // 非最后一段：只存位置
  }
  for (const pid of targets) {
    if ((progressStates[pid] || 'new') !== 'new') continue;
    progressStates[pid] = 'listened';
    await post('/api/progress', { point_id: pid, state: 'listened' }).catch(() => {});
  }
}

function setupMediaSession(cid) {
  if (!('mediaSession' in navigator)) return;
  const hit = state.clipIndex.get(cid);
  navigator.mediaSession.metadata = new MediaMetadata({
    title: hit ? pointTitle(cid.split('-p')[0]) : cid,
    artist: hit ? (hit.chap.name || '') : '',
    album: '考研陪跑',
  });
  navigator.mediaSession.setActionHandler('play', () => audio.play());
  navigator.mediaSession.setActionHandler('pause', () => audio.pause());
  navigator.mediaSession.setActionHandler('seekbackward', () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
  navigator.mediaSession.setActionHandler('seekforward', () => { audio.currentTime += 15; });
}

function paintPlayer() {
  const cid = current();
  const hit = cid ? state.clipIndex.get(cid) : null;
  document.getElementById('p-title').textContent = cid ? clipTitle(cid) : '—';
  document.getElementById('p-ctx').textContent = hit ? hit.chap.name : '未选择音频';
  document.getElementById('p-dur').textContent = fmt(audio.duration || (hit && hit.clip.dur) || 0);
  document.getElementById('p-cur').textContent = fmt(audio.currentTime);
  const pct = audio.duration ? (audio.currentTime / audio.duration) * 100 : 0;
  document.getElementById('p-fill').style.width = pct + '%';
  document.getElementById('p-play').textContent = audio.paused ? '▶' : '❚❚';
}

function paintQueue() {
  const list = document.getElementById('queue-list');
  if (!list) return;
  document.getElementById('queue-meta').textContent = queue.length ? `${queue.length} 段` : '';
  if (!queue.length) {
    list.innerHTML = '<div class="empty">队列为空（选"按章节"或等计划生成）。</div>';
    return;
  }
  // 按科目分组渲染（播放顺序保持不变，仅视觉分组）
  const order = [];
  const groups = new Map();
  queue.forEach((cid) => {
    const hit = state.clipIndex.get(cid);
    const sid = hit ? hit.subj.id : '?';
    if (!groups.has(sid)) {
      groups.set(sid, []);
      order.push(sid);
    }
    groups.get(sid).push({ cid, hit });
  });
  const rowHtml = ({ cid, hit }, i) => {
    const tier = hit && hit.chap.tier ? Math.min(hit.chap.tier, 3) : 3;
    const cur = cid === current() ? '<span class="chip g">当前</span>' : '';
    const done = posMap[cid] && posMap[cid].plays ? '<span class="small">✓</span>' : '';
    const dur = `<span class="lsmall">${fmt(hit && hit.clip.dur)}</span>`;
    const kind = hit && hit.isChapter
      ? `<span class="lsmall">串讲·${(hit.point_ids || []).length}点</span>` : '';
    return `<div class="lrow" onclick="window.kyPlayer.playClip('${cid}')">
      <span class="dot d${tier}"></span>
      <b class="lt">${clipTitle(cid)}</b>
      ${kind}${cur}${dur}${done}</div>`;
  };
  list.innerHTML = order.map((sid) => {
    const items = groups.get(sid);
    const name = items[0].hit ? items[0].hit.subj.name : '未知科目';
    return `<div class="qgroup"><b>${name}</b><span class="small">${items.length} 段</span></div>
      <div class="qbody">${items.map(rowHtml).join('')}</div>`;
  }).join('');
}

/* 事件与节流保存 */
audio.addEventListener('error', () => {
  if (!navigator.onLine) {
    document.getElementById('p-ctx').textContent =
      '离线中：该段未下载 · 联网后可播（看页「下载本章音频」可离线）';
  }
});
audio.addEventListener('ended', onEnded);
audio.addEventListener('timeupdate', () => {
  paintPlayer();
  if (++saveTick % 50 === 0 && !audio.paused) savePos(current(), false);  // 约每 5s
});
audio.addEventListener('play', paintPlayer);
audio.addEventListener('pause', () => { paintPlayer(); savePos(current(), false); });
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') savePos(current(), false);
});

export const kyPlayer = {
  toggle: () => (audio.paused ? audio.play().catch(() => {}) : audio.pause()),
  seek: (d) => { audio.currentTime = Math.max(0, audio.currentTime + d); },
  next, prev, playClip,
  setQueue,
  promptGo: () => { cancelPrompt(); next(); },
  promptReplay: (cid) => {
    cancelPrompt();
    const i = queue.indexOf(cid);
    if (i >= 0) idx = i;
    loadAndPlay();
  },
  cycleRate(btn) {
    const seq = [1.0, 1.25, 1.5, 2.0];
    rate = seq[(seq.indexOf(rate) + 1) % seq.length];
    audio.playbackRate = rate;
    btn.textContent = rate.toFixed(2).replace(/0$/, '') + 'x';
  },
  toggleLoop(btn) { loopOne = !loopOne; btn.classList.toggle('on', loopOne); },
  _state: () => ({ idx, queue: queue.slice(), cid: current(), pos: audio.currentTime,
                   progress: { ...progressStates } }),
  _fireEnded: () => onEnded(),
};
window.kyPlayer = kyPlayer;

// ---------- 离线音频（按章下载到 Cache Storage；SW 对 /audio 缓存优先） ----------
// 记录随 content 版本走：重生成音频后版本变化 → 已下载章显示为未下载，提示重新下载
const OFFLINE_LS = 'ky_audio_chaps';

function contentVer() { return (state.content && state.content.version) || 'v1'; }

function offlineSet() {
  try {
    const raw = JSON.parse(localStorage.getItem(OFFLINE_LS) || 'null');
    if (!raw) return new Set();
    if (Array.isArray(raw)) return new Set();                 // 旧格式无版本信息 → 视为失效
    if (raw.ver !== contentVer()) return new Set();           // 版本不符 → 提示重新下载
    return new Set(raw.chaps || []);
  } catch (e) { return new Set(); }
}
function offlineSave(s) {
  localStorage.setItem(OFFLINE_LS, JSON.stringify({ ver: contentVer(), chaps: [...s] }));
}

function chapterClipSrcs(chapId) {
  const srcs = [];
  for (const subj of state.content.subjects) {
    for (const ch of subj.chapters || []) {
      if (ch.id !== chapId) continue;
      for (const c of ch.listen || []) srcs.push(c.src);
      for (const p of ch.points || []) for (const a of p.audio || []) srcs.push(a.src);
    }
  }
  return srcs;
}

export async function downloadChapter(chapId) {
  const ver = (state.content && state.content.version) || 'v1';
  const cache = await caches.open('ky-audio-' + ver);
  const srcs = chapterClipSrcs(chapId);
  let ok = 0;
  for (const s of srcs) {
    try { await cache.add('/' + s); ok += 1; } catch (e) { /* 单段失败不阻塞整章 */ }
  }
  if (srcs.length && ok === srcs.length) {
    const set = offlineSet(); set.add(chapId); offlineSave(set);
  }
  return { ok, total: srcs.length };
}

export function offlineStatus(chapId) { return offlineSet().has(chapId); }

export async function clearOffline() {
  for (const k of await caches.keys()) {
    if (k.startsWith('ky-audio-')) await caches.delete(k);
  }
  localStorage.removeItem(OFFLINE_LS);
}

async function downloadFromCard(chapId, btn) {
  const old = btn.textContent;
  btn.textContent = '下载中…';
  const r = await downloadChapter(chapId);
  btn.textContent = r.total && r.ok === r.total ? '已离线 ✓' : `部分失败 ${r.ok}/${r.total}`;
  if (!r.total) btn.textContent = old;
}

window.kyOffline = { download: downloadChapter, status: offlineStatus,
                     clear: clearOffline, downloadFromCard };

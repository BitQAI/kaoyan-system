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
  paintPlayer();
  paintQueue();
  setupMediaSession(cid);
}

function onEnded() {
  const cid = current();
  if (loopOne) { audio.currentTime = 0; audio.play().catch(() => {}); return; }
  savePos(cid, true);
  markPointIfLastPart(cid);
  next();
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

async function markPointIfLastPart(cid) {
  const hit = state.clipIndex.get(cid);
  if (!hit) return;
  const clips = hit.point.audio || [];
  const lastSrc = clips.length ? clips[clips.length - 1].src : '';
  const lastCid = lastSrc.replace(/^audio\//, '').replace(/\.mp3$/, '');
  if (cid !== lastCid) return;                     // 非最后一段：只存位置
  const pid = hit.point.id;
  if ((progressStates[pid] || 'new') !== 'new') return;
  progressStates[pid] = 'listened';
  await post('/api/progress', { point_id: pid, state: 'listened' }).catch(() => {});
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
  list.innerHTML = queue.map((cid, i) => {
    const hit = state.clipIndex.get(cid);
    const tier = hit && hit.chap.tier ? Math.min(hit.chap.tier, 3) : 3;
    const cur = i === idx ? '<span class="chip g">当前</span>' : '';
    const done = posMap[cid] && posMap[cid].plays ? '<span class="small">✓</span>' : '';
    return `<div class="row" onclick="window.kyPlayer.playClip('${cid}')">
      <span class="dot d${tier}"></span>
      <div class="t"><b>${clipTitle(cid)}</b>
        <span class="small">${hit ? hit.chap.name.slice(0, 12) : ''} · ${fmt(hit && hit.clip.dur)}</span></div>
      ${cur}${done}</div>`;
  }).join('');
}

/* 事件与节流保存 */
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

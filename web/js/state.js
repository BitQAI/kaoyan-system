import { get } from './api.js';

export const state = {
  content: null,
  pointIndex: new Map(),      // point_id -> {subj, chap, point}
  clipIndex: new Map(),       // clip_id -> {point, clip}
  stats: null,
  plan: null,
};

export async function loadContent(force = false) {
  if (state.content && !force) return state.content;
  const data = await get('/api/content');
  state.content = data;
  state.pointIndex.clear();
  state.clipIndex.clear();
  for (const subj of data.subjects || []) {
    for (const chap of subj.chapters || []) {
      for (const p of chap.points || []) {
        state.pointIndex.set(p.id, { subj, chap, point: p });
        for (const a of p.audio || []) {
          const clipId = a.src.replace(/^audio\//, '').replace(/\.mp3$/, '');
          state.clipIndex.set(clipId, { point: p, clip: a, chap });
        }
      }
    }
  }
  return data;
}

export function pointTitle(pointId) {
  const hit = state.pointIndex.get(pointId);
  return hit ? hit.point.text.slice(0, 30) : pointId;
}

export function clipTitle(clipId) {
  const hit = state.clipIndex.get(clipId);
  if (!hit) return clipId;
  const part = clipId.includes('-p') ? `（${clipId.split('-p')[1]}）` : '';
  return hit.point.text.slice(0, 26) + part;
}

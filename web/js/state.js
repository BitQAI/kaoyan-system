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
          state.clipIndex.set(clipId, { point: p, clip: a, chap, subj });
        }
      }
      for (const c of chap.listen || []) {
        const clipId = c.src.replace(/^audio\//, '').replace(/\.mp3$/, '');
        state.clipIndex.set(clipId, { chap, subj, clip: c, isChapter: true,
                                      point_ids: c.point_ids || [] });
      }
    }
  }
  return data;
}

/** 展示用短标题：去掉括号内的解释性罗列，兼容被切碎的续段与超长文本。 */
export function shortTitle(text) {
  const cap = (s) => (s.length > 26 ? s.slice(0, 26) + '…' : s);
  let t = (text || '').trim();
  const open = t.indexOf('（');
  if (open >= 2) {
    const head = t.slice(0, open).replace(/[，,、；;。：:]+$/, '');
    if (head.length >= 2) return cap(head);
  }
  if (open < 0) {
    t = t.replace(/）\s*$/, '');
  }
  return cap(t);
}

export function pointTitle(pointId) {
  const hit = state.pointIndex.get(pointId);
  return hit ? shortTitle(hit.point.text) : pointId;
}

export function clipTitle(clipId) {
  const hit = state.clipIndex.get(clipId);
  if (!hit) return clipId;
  if (hit.isChapter) {
    const suffix = clipId.includes('-c') ? `（${clipId.split('-c')[1]}）` : '';
    return hit.chap.name + ' · 串讲' + suffix;
  }
  const part = clipId.includes('-p') ? `（${clipId.split('-p')[1]}）` : '';
  return shortTitle(hit.point.text) + part;
}

const TAG_PRIORITY = ['易错', '常考', '高频', '必掌握', '重点', '基础', '机制', '理解', '了解'];

export function tagClass(t) {
  if (['易错', '常考', '高频', '必掌握'].includes(t)) return 'r';
  if (['重点', '理解'].includes(t)) return 'o';
  if (t === '机制') return 'b';
  if (t === '了解') return '';
  return 'g';
}

/** 按优先级取前 max 个徽标（html）。传入 point 或 tags 数组。 */
export function tagChips(pointOrTags, max = 2) {
  const tags = Array.isArray(pointOrTags) ? pointOrTags : (pointOrTags && pointOrTags.tags) || [];
  const sorted = [...tags].sort((a, b) => {
    const ia = TAG_PRIORITY.indexOf(a); const ib = TAG_PRIORITY.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  return sorted.slice(0, max).map((t) => `<span class="chip ${tagClass(t)}">${t}</span>`).join('');
}

export function pointTags(pointId) {
  const hit = state.pointIndex.get(pointId);
  return hit ? hit.point.tags || [] : [];
}

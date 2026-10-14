import { get, post } from './api.js';
import { state } from './state.js';

const LS_KEY = 'ky_exam_run';
let paper = null;          // 服务端卷面
let flat = [];             // 展平题目/卡片
let run = null;            // {exam_id, responses:{}, verdicts:{}, i, started_at}

const PAPERS = [
  { key: '315-objective', label: '315 化学（农）客观卷', desc: '30 单选 + 20 填空 · 90 分钟 · 100 分', subject: '315' },
  { key: '101-objective', label: '101 政治客观卷', desc: '16 单选 + 17 多选 · 60 分钟 · 50 分', subject: '101' },
  { key: '812-subjective', label: '812 植物生理主观卷', desc: '名解 6 + 简答 6 + 论述 2 · 90 分钟 · 自评', subject: '812' },
];

function saveRun() {
  if (run) localStorage.setItem(LS_KEY, JSON.stringify(run));
}
const clearSaved = () => localStorage.removeItem(LS_KEY);
const loadSaved = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (e) { return null; } };

export function entry() {
  window.kyGo('exam');
  const saved = loadSaved();
  const body = document.getElementById('exam-body');
  if (saved && !saved.finished) {
    body.innerHTML = `<div class="card"><h3>有未完成的考试</h3>
      <p class="small">${saved.subject === '315' ? '315 客观卷' : saved.subject === '101' ? '101 客观卷' : '812 主观卷'}
        · 进度 ${saved.i} 题</p>
      <button class="btn" onclick="window.kyExam.resumePaper()">继续考试</button>
      <button class="btn ghost" style="margin-left:8px" onclick="window.kyExam.abandon()">放弃</button></div>`;
    return;
  }
  body.innerHTML = `<div class="card"><h3>选择试卷 <span class="small">按真题题型组装</span></h3>` +
    PAPERS.map((p) => `<div class="row"><div class="t"><b>${p.label}</b><span class="small">${p.desc}</span></div>
      <button class="btn sm" onclick="window.kyExam.newPaper('${p.subject}','${p.key.split('-')[1]}')">开始</button></div>`).join('') +
    `</div>`;
}

async function newPaper(subject, kind) {
  const body = document.getElementById('exam-body');
  body.innerHTML = '<div class="card"><div class="empty">组卷中…</div></div>';
  let p;
  try {
    p = await post('/api/exam/new', { subject, kind });
  } catch (e) {
    body.innerHTML = `<div class="card"><div class="empty">组卷失败：${e.message}（题库可能不足）</div></div>`;
    return;
  }
  startWithPaper(p);
}

function startWithPaper(p, saved) {
  paper = p;
  flat = [];
  for (const s of p.sections) {
    for (const it of s.items) {
      flat.push({ ...it, _section: s.name, _type: s.type, _kind: s.kind, _score: s.score_per });
    }
  }
  run = saved || { exam_id: p.exam_id, subject: p.subject, responses: {}, verdicts: {}, i: 0,
                   started_at: Date.now(), finished: false };
  paintExam();
}

async function resumePaper() {
  const saved = loadSaved();
  if (!saved) return entry();
  const body = document.getElementById('exam-body');
  body.innerHTML = '<div class="card"><div class="empty">恢复中…</div></div>';
  const got = await get(`/api/exam/${saved.exam_id}`).catch(() => null);
  if (!got || got.finished) { clearSaved(); return entry(); }
  startWithPaper(got.paper, saved);
}

function abandon() { clearSaved(); entry(); }

function fmtClock(sec) {
  sec = Math.max(0, sec);
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;
}

function remains() {
  const total = (paper.time_limit_min || 90) * 60;
  return total - Math.floor((Date.now() - run.started_at) / 1000);
}

function paintExam() {
  const body = document.getElementById('exam-body');
  if (!flat.length) {
    body.innerHTML = '<div class="card"><div class="empty">该卷暂无可用题目（对应题型内容尚未入库）。</div></div>'
      + '<button class="btn" style="width:100%" onclick="window.kyExam.entry()">返回试卷选择</button>';
    return;
  }
  const q = flat[run.i];
  if (!q) return paintResultDraft();
  const left = remains();
  const head = `<div class="card" style="position:sticky;top:60px;z-index:5">
    <h3>${q._section} · ${run.i + 1}/${flat.length}
      <span class="small" id="exam-clock">${left > 0 ? '剩 ' + fmtClock(left) : '时间到'}</span></h3></div>`;
  let bodyHtml = '';
  if (q._type === 'card') {
    const v = run.verdicts[q.id];
    bodyHtml = `<div class="flip" onclick="this.classList.toggle('f')">
      <div class="inner"><div class="face"><b>${q.front}</b><p class="small">点击翻面查看参考答案</p></div>
      <div class="face back"><span class="small">参考答案（AI 生成，请对照教材）</span><p>${q.back}</p></div>
      </div></div>
    <div style="display:flex;gap:8px;margin-top:10px">
      <button class="btn" style="flex:1;background:var(--green);${v === 'know' ? '' : 'opacity:.55'}" onclick="window.kyExam.verdict('${q.id}','know')">会了</button>
      <button class="btn" style="flex:1;background:var(--orange);${v === 'fuzzy' ? '' : 'opacity:.55'}" onclick="window.kyExam.verdict('${q.id}','fuzzy')">模糊</button>
      <button class="btn" style="flex:1;background:var(--red);${v === 'no' ? '' : 'opacity:.55'}" onclick="window.kyExam.verdict('${q.id}','no')">不会</button>
    </div>`;
  } else if (q._type === 'multi') {
    const picked = new Set(run.responses[q.id] || []);
    bodyHtml = q.options.map((o, i) =>
      `<div class="opt ${picked.has(i) ? 'pick' : ''}" onclick="window.kyExam.toggleMulti('${q.id}',${i},this)">
        <span class="k">${'ABCD'[i]}</span><span>${o}</span></div>`).join('');
  } else if (q._type === 'blank') {
    bodyHtml = (q.blanks || []).map((b, i) => {
      const v = (run.responses[q.id] || [])[i] || '';
      return `<div style="margin:8px 0"><input class="blank-input" value="${String(v).replace(/"/g, '&quot;')}"
        placeholder="${b.hint || `第 ${i + 1} 空`}"
        oninput="window.kyExam.setBlank('${q.id}',${i},this.value)"></div>`;
    }).join('');
  } else {
    const pick = run.responses[q.id];
    bodyHtml = q.options.map((o, i) =>
      `<div class="opt ${pick === i ? 'pick' : ''}" onclick="window.kyExam.pickSingle('${q.id}',${i})">
        <span class="k">${'ABCD'[i]}</span><span>${o}</span></div>`).join('');
  }
  body.innerHTML = head + `<div class="card"><p style="margin:4px 0 2px"><b>${q.stem || q.front}</b></p>${bodyHtml}</div>
    <div style="display:flex;gap:8px;margin-bottom:20px">
      <button class="btn ghost" style="flex:1" onclick="window.kyExam.prev()" ${run.i === 0 ? 'disabled' : ''}>上一题</button>
      ${run.i < flat.length - 1
        ? '<button class="btn" style="flex:2" onclick="window.kyExam.next()">下一题</button>'
        : ''}
      <button class="btn" style="flex:1;background:var(--red)" onclick="window.kyExam.submit()">交卷</button>
    </div>`;
  clearInterval(window.__kyExamTimer);
  window.__kyExamTimer = setInterval(() => {
    const el = document.getElementById('exam-clock');
    if (!el || !run) return;
    const l = remains();
    el.textContent = l > 0 ? '剩 ' + fmtClock(l) : '时间到（可继续作答）';
  }, 1000);
}

function paintResultDraft() {
  document.getElementById('exam-body').innerHTML =
    '<div class="card"><div class="empty">已到最后一题，请点击交卷。</div></div>';
}

async function submit() {
  clearInterval(window.__kyExamTimer);
  const body = document.getElementById('exam-body');
  body.innerHTML = '<div class="card"><div class="empty">判分中…</div></div>';
  const responses = Object.entries(run.responses)
    .map(([item_id, response]) => ({ item_id, response }));
  const verdicts = Object.entries(run.verdicts).map(([card_id, verdict]) => ({ card_id, verdict }));
  let r;
  try {
    r = await post('/api/exam/submit', { exam_id: run.exam_id, responses, verdicts });
  } catch (e) {
    body.innerHTML = `<div class="card"><div class="empty">交卷失败：${e.message}</div></div>`;
    return;
  }
  // 错题自动入错题本（走 attempt 端点 → 触发错题本/复习挂钩）
  let added = 0;
  for (const qid of r.wrong_quiz_ids || []) {
    const resp = run.responses[qid];
    if (resp === undefined) continue;
    await post('/api/quiz/attempt', { quiz_id: qid, response: resp }).catch(() => {});
    added += 1;
  }
  run.finished = true;
  clearSaved();
  const chapNames = {};
  for (const subj of state.content.subjects) for (const ch of subj.chapters) chapNames[ch.id] = ch.name;
  const secRows = Object.entries(r.per_section).map(([n, v]) =>
    `<tr><td>${n}</td><td>${v.earned} / ${v.total}</td></tr>`).join('');
  const chapRows = Object.entries(r.per_chapter).sort((a, b) => (b[1].n - a[1].n) === 0
    ? (a[1].correct / Math.max(a[1].n, 1)) - (b[1].correct / Math.max(b[1].n, 1))
    : b[1].n - a[1].n).slice(0, 12).map(([cid, v]) =>
    `<tr><td>${chapNames[cid] || cid}</td><td>${v.correct}/${v.n}（${Math.round(v.correct / v.n * 100)}%）</td></tr>`).join('');
  body.innerHTML = `<div class="card"><h3>成绩单</h3>
    <div class="stat">${r.score} <span class="small" style="font-size:14px">/ ${r.total} 分</span></div>
    <table style="margin-top:10px">${secRows}</table>
    ${added ? `<p class="small">✗ 错题 ${added} 道已自动加入错题本（可在「测」中重练）</p>` : ''}
    </div>
    <div class="card"><h3>按章正确率</h3><table>${chapRows || '<tr><td>—</td><td>—</td></tr>'}</table></div>
    <button class="btn" style="width:100%" onclick="window.kyExam.entry()">返回试卷选择</button>`;
}

export const kyExam = {
  entry, newPaper, resumePaper, abandon, submit,
  prev() { if (run.i > 0) { run.i -= 1; saveRun(); paintExam(); } },
  next() { if (run.i < flat.length - 1) { run.i += 1; saveRun(); paintExam(); } },
  pickSingle(qid, i) { run.responses[qid] = i; saveRun(); paintExam(); },
  toggleMulti(qid, i, el) {
    const cur = new Set(run.responses[qid] || []);
    if (cur.has(i)) cur.delete(i); else cur.add(i);
    run.responses[qid] = [...cur];
    saveRun();
    el.classList.toggle('pick');
  },
  setBlank(qid, i, v) {
    const cur = run.responses[qid] || [];
    cur[i] = v;
    run.responses[qid] = cur;
    saveRun();
  },
  verdict(qid, v) { run.verdicts[qid] = v; saveRun(); paintExam(); },
};

window.kyExam = kyExam;

import { get, post } from './api.js';
import { state, tagChips } from './state.js';

let run = null;          // {items, i, right, mode, chapter, flagged:Set}
let waiting = false;
let timer = null;
const LS_KEY = 'ky_quiz_run';
const today = () => new Date().toISOString().slice(0, 10);

function quizById(id) {
  for (const subj of state.content.subjects)
    for (const ch of subj.chapters)
      for (const q of ch.quiz || []) if (q.id === id) return q;
  return null;
}

function saveRun() {
  if (!run) return;
  localStorage.setItem(LS_KEY, JSON.stringify({
    at: today(), mode: run.mode, chapter: run.chapter || null,
    itemIds: run.items.map((q) => q.id), i: run.i, right: run.right,
    flagged: [...run.flagged],
  }));
}

function loadSaved() {
  try {
    const s = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
    if (s && s.at === today() && s.i < s.itemIds.length) return s;
  } catch (e) { /* 忽略坏数据 */ }
  return null;
}

const clearSaved = () => localStorage.removeItem(LS_KEY);

export async function renderTest() {
  const wrong = await get('/api/quiz/wrong').catch(() => ({ items: [] }));
  const w = wrong.items || [];
  document.getElementById('wrong-count').textContent =
    w.length ? `${w.length} 题待清 · 连对 2 次自动出本` : '全部清空 · 保持住';
  const saved = loadSaved();
  document.getElementById('resume-box').innerHTML = saved ? `<div class="card">
    <div class="row"><div class="t"><b>继续上次练习</b>
      <span class="small">进度 ${saved.i}/${saved.itemIds.length} · 对 ${saved.right}</span></div>
      <button class="btn sm" onclick="window.kyQuiz.resume()">继续</button>
      <button class="btn sm ghost" onclick="window.kyQuiz.discard()">重新开始</button></div></div>` : '';
  document.getElementById('test-modes').innerHTML = `
    <div class="lrow" onclick="window.kyQuiz.start('chapter')">
      <span class="dot d1"></span><b class="lt">选择题练习</b>
      <span class="lsmall">按章节 · 今日优先</span><span class="caret">›</span></div>
    <div class="lrow" onclick="window.kyQuiz.start('wrong')">
      <span class="dot" style="background:var(--red)"></span><b class="lt">错题重练</b>
      <span class="lsmall">${w.length ? `${w.length} 题待清` : '暂无错题'}</span><span class="caret">›</span></div>
    <div class="lrow" onclick="window.kyQuiz.start('favorites')">
      <span class="dot" style="background:var(--orange)"></span><b class="lt">收藏重练</b>
      <span class="lsmall">来自收藏</span><span class="caret">›</span></div>
    <div class="lrow" onclick="window.kyExam&&window.kyExam.entry()">
      <span class="dot" style="background:var(--green)"></span><b class="lt">模拟考试</b>
      <span class="lsmall">真题题型 · 限时计分</span><span class="caret">›</span></div>`;
  await renderCards();
}

async function start(mode) {
  const chapter = mode === 'chapter' ? ((state.plan && state.plan.look && state.plan.look[0]) || '').slice(0, 6) : null;
  const q = new URLSearchParams({ mode, n: '15' });
  if (mode === 'chapter' && chapter) q.set('chapter', chapter);
  const items = (await get('/api/quiz/run?' + q)).items || [];
  if (!items.length) {
    document.getElementById('quiz-run').innerHTML =
      '<div class="card"><div class="empty">没有可练的题目（换个模式或等内容就绪）。</div></div>';
    return;
  }
  run = { items, i: 0, right: 0, mode, chapter, flagged: new Set() };
  saveRun();
  paintQuiz();
}

function resume() {
  const s = loadSaved();
  if (!s) return;
  const items = s.itemIds.map(quizById).filter(Boolean);
  if (!items.length) { clearSaved(); renderTest(); return; }
  run = { items, i: Math.min(s.i, items.length), right: s.right, mode: s.mode,
          chapter: s.chapter, flagged: new Set(s.flagged || []) };
  paintQuiz();
}

function discard() { clearSaved(); renderTest(); }

function paintQuiz() {
  const box = document.getElementById('quiz-run');
  if (!run || run.i >= run.items.length) {
    if (run) {
      clearSaved();
      box.innerHTML = `<div class="card"><h3>完成 🎉</h3>
        <p class="small">共 ${run.items.length} 题，答对 ${run.right} 题${run.flagged.size ? ` · 标记疑问题 ${run.flagged.size}` : ''}</p>
        <button class="btn" onclick="window.kyQuiz.reload()">回到训练库</button></div>`;
      run = null;
    }
    return;
  }
  const q = run.items[run.i];
  const hit = q.point_id && state.pointIndex.get(q.point_id);
  const media = (q.media || []).map((m) => m.src ? `<div class="media"><img src="/${m.src}" alt=""></div>` : '').join('');
  const typeLabel = { single: '单选', multi: '多选', blank: '填空' }[q.type || 'single'];
  let bodyHtml = '';
  if (q.type === 'multi') {
    bodyHtml = q.options.map((o, i) =>
      `<div class="opt" data-i="${i}" onclick="window.kyQuiz.toggleOpt(this)">
        <span class="k">${'ABCD'[i]}</span><span>${o}</span></div>`).join('')
      + '<button class="btn" style="width:100%;margin-top:6px" onclick="window.kyQuiz.submitMulti()">提交答案</button>';
  } else if (q.type === 'blank') {
    bodyHtml = (q.blanks || []).map((b, i) =>
      `<div style="margin:8px 0"><input class="blank-input" id="bl-${i}" placeholder="${b.hint || `第 ${i + 1} 空`}"></div>`).join('')
      + '<button class="btn" style="width:100%;margin-top:6px" onclick="window.kyQuiz.submitBlank()">提交答案</button>';
  } else {
    bodyHtml = q.options.map((o, i) =>
      `<div class="opt" data-i="${i}" onclick="window.kyQuiz.pick(this,${i})">
        <span class="k">${'ABCD'[i]}</span><span>${o}</span></div>`).join('');
  }
  box.innerHTML = `<div class="card">
    <h3>${typeLabel} ${run.i + 1}/${run.items.length}
      <span class="small">对 ${run.right}${run.flagged.size ? ` · <b style="color:var(--orange)">标记 ${run.flagged.size}</b>` : ''}</span></h3>
    ${hit ? `<div class="small" style="margin:2px 0">${tagChips(hit.point, 3)}<span style="color:var(--muted)"> 关联：${hit.point.text.slice(0, 16)}</span></div>` : ''}
    <p style="margin:4px 0 2px"><b>${q.stem}</b></p>
    ${media}${bodyHtml}
    <div class="explain" id="exp"></div>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn sm ghost" onclick="window.kyQuiz.flag()">标记疑虑</button>
      <button class="btn sm ghost" onclick="window.kyQuiz.skip()">跳过</button>
    </div></div>`;
}

const currentQ = () => (run && run.i < run.items.length ? run.items[run.i] : null);

function next() {
  if (timer) { clearTimeout(timer); timer = null; }
  if (!run) return;
  run.i += 1;
  saveRun();
  paintQuiz();
}

async function judge(response, opts = {}) {
  if (waiting) return;
  const q = currentQ();
  if (!q) return;
  waiting = true;
  const r = await post('/api/quiz/attempt', { quiz_id: q.id, response });
  if (r.correct) run.right += 1;
  const exp = document.getElementById('exp');
  exp.style.display = 'block';
  if (q.type === 'multi') {
    document.querySelectorAll('#quiz-run .opt').forEach((o) => {
      const i = +o.dataset.i;
      o.classList.remove('pick');
      if (r.answer.includes(i)) o.classList.add('right');
      else if (o.classList.contains('picked')) o.classList.add('wrong');
    });
  } else if (q.type === 'blank') {
    const yours = (response || []).map((x) => x || '（空）').join(' | ');
    exp.innerHTML = `${r.correct ? '✓ 答对' : `✗ 参考答案：${[].concat(r.answer).join(' | ')}<br>你的答案：${yours}`}
      <br>${r.explain || ''}`;
  } else {
    const optsEls = document.querySelectorAll('#quiz-run .opt');
    optsEls.forEach((o) => o.classList.remove('pick'));
    optsEls[response] && optsEls[response].classList.add(r.correct ? 'right' : 'wrong');
    if (!r.correct && optsEls[r.answer]) optsEls[r.answer].classList.add('right');
    exp.innerHTML = `${r.correct ? '✓ 答对' : '✗ 正确答案 ' + 'ABCD'[r.answer]}　${r.explain || ''}`;
  }
  if (r.correct || q.type !== 'blank') {
    waiting = false;
    timer = setTimeout(next, r.correct ? 900 : 1800);
  } else {
    // 填空答错：提供自评兜底与手动下一题
    exp.innerHTML += `<div style="margin-top:8px;display:flex;gap:8px">
      <button class="btn sm" style="background:var(--green)" onclick="window.kyQuiz.selfPass()">我答对了</button>
      <button class="btn sm ghost" onclick="window.kyQuiz.nextNow()">下一题</button></div>`;
    waiting = false;
  }
}

export const kyQuiz = {
  start, resume, discard,
  pick: (el, i) => { el.classList.add('pick'); judge(i); },
  toggleOpt: (el) => { el.classList.toggle('picked'); el.classList.toggle('pick'); },
  submitMulti() {
    const picked = [...document.querySelectorAll('#quiz-run .opt.picked')].map((o) => +o.dataset.i);
    if (!picked.length) return;
    judge(picked);
  },
  submitBlank() {
    const inputs = [...document.querySelectorAll('#quiz-run .blank-input')].map((x) => x.value);
    if (inputs.every((x) => !x.trim())) return;
    judge(inputs);
  },
  selfPass() { if (run) { run.right += 1; saveRun(); } next(); },
  nextNow: next,
  skip: next,
  flag() {
    const q = currentQ();
    if (!q || !run) return;
    if (run.flagged.has(q.id)) run.flagged.delete(q.id); else run.flagged.add(q.id);
    saveRun();
    paintQuiz();
  },
  reload: renderTest,
};

window.kyQuiz = kyQuiz;

// ---------- 背题卡（自评） ----------

const CARDS_LS = 'ky_cards_done';
let cardCursor = 0;
let cardStep = 0;              // 背题卡三步：0 问题 / 1 关键词锚点 / 2 完整答案
let curCard = null;

function cardsDone() {
  try { return new Set(JSON.parse(localStorage.getItem(CARDS_LS) || '[]')); } catch (e) { return new Set(); }
}

function saveCardsDone(s) { localStorage.setItem(CARDS_LS, JSON.stringify([...s])); }

function resetCards() { localStorage.removeItem(CARDS_LS); renderCards(); }

async function renderCards() {
  const box = document.getElementById('card-box');
  const all = [];
  for (const subj of state.content.subjects) {
    for (const c of subj.chapters) {
      for (const cd of (c.cards || [])) {
        if (state.pointIndex.has(cd.point_id)) all.push(cd);
      }
    }
  }
  if (!all.length) { box.innerHTML = '<div class="empty">暂无背题卡</div>'; return; }
  const done = cardsDone();
  const doneN = all.filter((cd) => done.has(cd.id)).length;
  // 游标轮转：跳过未完成的卡（含「模糊」重出的），避免连续出现同一张
  let card = null;
  for (let k = 0; k < all.length; k++) {
    const cd = all[(cardCursor + k) % all.length];
    if (!done.has(cd.id)) {
      card = cd;
      cardCursor = (cardCursor + k + 1) % all.length;
      break;
    }
  }
  if (!card) {
    box.dataset.cardId = '';
    box.innerHTML = `<div class="empty">本轮 ${all.length} 张已过完 🎉</div>
      <div style="text-align:center"><button class="btn sm ghost" onclick="window.kyQuiz.resetCards()">重新开始一轮</button></div>`;
    return;
  }
  box.dataset.cardId = card.id;
  curCard = card;
  cardStep = 0;
  const hit = state.pointIndex.get(card.point_id);
  const ctx = hit ? `${hit.subj.name.slice(0, 6)} · ${hit.chap.name.slice(0, 12)}` : '';
  box.innerHTML = `
    <div class="ccard-bar"><span class="small">${ctx}</span>
      <span class="small">${doneN + 1}/${all.length}</span></div>
    <div class="stepcard">
      <div class="small">${card.kind ? `<span class="chip b">${card.kind}</span>` : ''}${hit ? tagChips(hit.point, 2) : ''}</div>
      <b class="sc-front">${card.front}</b>
      <div id="sc-body"></div>
      <div id="sc-acts"></div>
    </div>`;
  paintCardStep();
}

function paintCardStep() {
  const body = document.getElementById('sc-body');
  const acts = document.getElementById('sc-acts');
  if (!body || !acts || !curCard) return;
  const hit = state.pointIndex.get(curCard.point_id);
  if (cardStep === 0) {
    body.innerHTML = '<p class="small">先在心里回忆一遍，对不上再看提示。</p>';
    acts.innerHTML = '<div class="sc-btns">' +
      '<button class="btn" onclick="window.kyQuiz.cardStep(1)">看关键词</button>' +
      '<button class="btn ghost" onclick="window.kyQuiz.cardStep(2)">直接看答案</button></div>';
  } else if (cardStep === 1) {
    const ks = (hit && hit.point.keywords) || [];
    body.innerHTML = ks.length
      ? `<div class="anchors">${ks.map((k) => `<span class="chip b">${k}</span>`).join('')}</div>
         <p class="small">顺着锚点把内容串起来，再对答案。</p>`
      : '<p class="small">（暂无关键词锚点，直接看答案吧）</p>';
    acts.innerHTML = '<div class="sc-btns">' +
      '<button class="btn" onclick="window.kyQuiz.cardStep(2)">看完整答案</button>' +
      '<button class="btn ghost" onclick="window.kyQuiz.cardStep(0)">回到问题</button></div>';
  } else {
    body.innerHTML = `<div class="sc-answer"><span class="small">答案（AI 生成，请对照教材）</span>
      <p>${curCard.back}</p></div>`;
    acts.innerHTML = `<div class="sc-btns">
      <button class="btn sm" style="flex:1;background:var(--green)" onclick="window.kyQuiz.verdict('know')">会了</button>
      <button class="btn sm" style="flex:1;background:var(--orange)" onclick="window.kyQuiz.verdict('fuzzy')">模糊</button>
      <button class="btn sm" style="flex:1;background:var(--red)" onclick="window.kyQuiz.verdict('no')">不会</button>
      <button class="btn sm ghost" onclick="window.kyQuiz.verdict('skip')">跳过</button></div>`;
  }
}

async function verdict(v) {
  const box = document.getElementById('card-box');
  const cardId = box.dataset.cardId;
  if (!cardId) return;
  if (v !== 'skip') {
    await post('/api/cards/review', { card_id: cardId, verdict: v }).catch(() => {});
  }
  if (v !== 'fuzzy') {                     // 模糊的卡片留到下一轮再出现
    const done = cardsDone();
    done.add(cardId);
    saveCardsDone(done);
  }
  cardStep = 0;
  renderCards();
}

kyQuiz.verdict = verdict;
kyQuiz.resetCards = resetCards;
kyQuiz.cardStep = (n) => { cardStep = n; paintCardStep(); };

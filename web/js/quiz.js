import { get, post } from './api.js';
import { state, tagChips } from './state.js';

let run = null;       // 当前做题会话
let waiting = false;

export async function renderTest() {
  const wrong = await get('/api/quiz/wrong').catch(() => ({ items: [] }));
  const w = wrong.items || [];
  const byChap = {};
  for (const q of w) {
    const pid = q.point_id || '';
    const key = pid.slice(0, 6);
    byChap[key] = (byChap[key] || 0) + 1;
  }
  document.getElementById('wrong-count').textContent = w.length
    ? `${w.length} 题待清 · 连对 2 次自动出本` : '全部清空 · 保持住';
  document.getElementById('test-modes').innerHTML = `
    <div class="row"><div class="t"><b>选择题练习</b><span class="small">按章节 · 今日章节优先</span></div>
      <button class="btn sm" onclick="window.kyQuiz.start('chapter')">开始</button></div>
    <div class="row"><div class="t"><b>错题重练</b><span class="small" id="wrong-count-inline"></span></div>
      <button class="btn sm ghost" style="color:var(--red);background:var(--redbg)"
        onclick="window.kyQuiz.start('wrong')">重练</button></div>
    <div class="row"><div class="t"><b>收藏重练</b><span class="small">来自收藏的题目</span></div>
      <button class="btn sm ghost" onclick="window.kyQuiz.start('favorites')">开始</button></div>`;
  const inline = document.getElementById('wrong-count-inline');
  if (inline) inline.textContent = w.length ? `${w.length} 题待清` : '暂无错题';
  await renderCards();
}

async function renderCards() {
  const box = document.getElementById('card-box');
  const chap = (state.plan && state.plan.look && state.plan.look[0] || '').slice(0, 6);
  let card = null;
  for (const subj of state.content.subjects) {
    for (const c of subj.chapters) {
      for (const cd of c.cards || []) {
        if (!chap || cd.id.startsWith('c' + (chap.replace('-', '')))) { card = cd; break; }
      }
      if (card) break;
    }
    if (card) break;
  }
  if (!card) {
    // 退而求其次：任意一张
    outer: for (const subj of state.content.subjects) {
      for (const c of subj.chapters) {
        if ((c.cards || []).length) { card = c.cards[0]; break outer; }
      }
    }
  }
  if (!card) { box.innerHTML = '<div class="empty">暂无背题卡</div>'; return; }
  box.dataset.cardId = card.id;
  const cardHit = card.point_id && state.pointIndex.get(card.point_id);
  box.innerHTML = `
    <div class="flip" id="flipcard" onclick="this.classList.toggle('f')">
      <div class="inner">
        <div class="face"><div class="small">${cardHit ? tagChips(cardHit.point, 3) : ''}</div>
          <b>${card.front}</b><p class="small">点击翻面查看答案</p></div>
        <div class="face back"><span class="small">答案（AI 生成，请对照教材）</span><p>${card.back}</p></div>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-top:10px">
      <button class="btn" style="flex:1;background:var(--green)" onclick="window.kyQuiz.verdict('know')">会了</button>
      <button class="btn" style="flex:1;background:var(--orange)" onclick="window.kyQuiz.verdict('fuzzy')">模糊</button>
      <button class="btn" style="flex:1;background:var(--red)" onclick="window.kyQuiz.verdict('no')">不会</button>
    </div>`;
}

async function start(mode) {
  const chapter = mode === 'chapter' ? ((state.plan && state.plan.look && state.plan.look[0]) || '').slice(0, 6) : null;
  const q = new URLSearchParams({ mode, n: '15' });
  if (mode === 'chapter' && chapter) q.set('chapter', chapter);
  const items = (await get('/api/quiz/run?' + q)).items || [];
  if (!items.length) {
    document.getElementById('quiz-run').innerHTML = '<div class="empty">没有可练的题目（换个模式或等内容就绪）。</div>';
    return;
  }
  run = { items, i: 0, right: 0 };
  paintQuiz();
}

function paintQuiz() {
  const box = document.getElementById('quiz-run');
  if (!run || run.i >= run.items.length) {
    box.innerHTML = run ? `<div class="card"><h3>完成 🎉</h3>
      <p class="small">共 ${run.items.length} 题，答对 ${run.right} 题</p>
      <button class="btn" onclick="window.kyQuiz.reload()">回到训练库</button></div>` : '';
    return;
  }
  const q = run.items[run.i];
  const media = (q.media || []).map((m) => m.src
    ? `<div class="media"><img src="/${m.src}" alt=""></div>` : '').join('');
  const hit = q.point_id && state.pointIndex.get(q.point_id);
  box.innerHTML = `<div class="card">
    <h3>选择题 ${run.i + 1}/${run.items.length} <span class="small">已完成 ${run.right} 对</span></h3>
    ${media}
    ${hit ? `<div class="small" style="margin:2px 0">${tagChips(hit.point, 3)}<span style="color:var(--muted)"> 关联：${hit.point.text.slice(0, 18)}</span></div>` : ''}
    <p style="margin:4px 0 2px"><b>${q.stem}</b></p>
    ${q.options.map((o, i) => `<div class="opt" data-i="${i}" onclick="window.kyQuiz.pick(this,${i})">
      <span class="k">${'ABCD'[i]}</span><span>${o}</span></div>`).join('')}
    <div class="explain" id="exp"></div>
  </div>`;
}

async function pick(el, i) {
  if (waiting) return;
  waiting = true;
  const q = run.items[run.i];
  const r = await post('/api/quiz/attempt', { quiz_id: q.id, chosen: i });
  if (r.correct) run.right += 1;
  const opts = document.querySelectorAll('#quiz-run .opt');
  opts.forEach((o) => o.classList.remove('pick'));
  el.classList.add('pick');
  el.classList.add(r.correct ? 'right' : 'wrong');
  if (!r.correct) opts[q.answer].classList.add('right');
  const exp = document.getElementById('exp');
  exp.style.display = 'block';
  exp.innerHTML = `${r.correct ? '✓ 答对' : '✗ 正确答案 ' + 'ABCD'[q.answer]}　${r.explain || ''}
    <br><button class="btn sm ghost" style="margin-top:8px"
      onclick="window.kyAI.open('quiz','${q.id}')">追问 AI</button>`;
  waiting = false;
  setTimeout(() => { run.i += 1; paintQuiz(); }, 900);
}

async function verdict(v) {
  const box = document.getElementById('card-box');
  const cardId = box.dataset.cardId;
  if (!cardId) return;
  await post('/api/cards/review', { card_id: cardId, verdict: v }).catch(() => {});
  renderTest();
}

export const kyQuiz = {
  start, pick, verdict,
  reload: renderTest,
};
window.kyQuiz = kyQuiz;

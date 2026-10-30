"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { postJson } from "@/lib/api";
import { answerHtml } from "@/lib/render";
import { clearResume, readResume, saveResume } from "@/lib/resume";
import { DEFAULT_SCOPE, readScope, scopeLabel, writeScope, type Scope } from "@/lib/scope";
import type { Card, Chapter, WordPayload } from "@/lib/types";
import { useAi } from "./AiProvider";
import { PriorityBadge, StarButton, uniqueLabels } from "./Badges";
import CardMeta from "./CardMeta";
import ClozeFace from "./ClozeFace";
import WordFace from "./WordFace";
import FavoritesPanel from "./FavoritesPanel";
import RangePicker from "./RangePicker";

const GRADES = ["秒答", "吃力", "忘了"] as const;

export default function MemoView({ sid, chapters }: { sid: string; chapters: Chapter[] }) {
  const [cards, setCards] = useState<Card[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [grades, setGrades] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [favOpen, setFavOpen] = useState(false);
  const [swipe, setSwipe] = useState<{ dx: number; dy: number; label: string } | null>(null);
  const dragRef = useRef({ x: 0, y: 0, active: false, moved: false });
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const ai = useAi();

  const chapterNames: Record<string, string> = {};
  chapters.forEach((c) => { chapterNames[c.id] = c.name; });

  const load = useCallback((next: Scope, resume = false) => {
    setLoading(true);
    postJson<{ items: Card[]; remaining: number }>("/api/queue/custom", {
      mode: "memo", subjects: [sid], chapters: next.chapters, limit: next.limit,
    })
      .then((d) => {
        let start = 0;
        if (resume) {
          const cardId = readResume("memo", sid);
          const i = cardId ? d.items.findIndex((c) => c.card_id === cardId) : -1;
          if (i > 0) start = i;
        }
        setCards(d.items);
        setRemaining(d.remaining);
        setIndex(start);
        setFlipped(false);
        setGrades([]);
      })
      .catch(() => { setCards([]); setRemaining(0); })
      .finally(() => setLoading(false));
  }, [sid]);

  useEffect(() => {
    const saved = readScope(sid);
    setScope(saved);
    load(saved, true);
  }, [sid, load]);

  useEffect(() => {
    if (!cards.length) return;
    const current = cards[index];
    if (current) saveResume("memo", sid, current.card_id);
    else clearResume("memo", sid);
  }, [cards, index, sid]);

  function applyScope(next: Scope) {
    setScope(next);
    writeScope(sid, next);
    setPickerOpen(false);
    load(next);
  }

  const card = cards[index];
  const wordPayload = (card?.payload as WordPayload | undefined)?.type
    ? (card.payload as WordPayload) : null;
  const isCloze = card?.kind === "默写";

  const grade = useCallback((result: string) => {
    if (!card) return;
    setGrades((g) => [...g, result]);
    setFlipped(false);
    setIndex((i) => i + 1);
    void postJson("/api/progress/card", { card_id: card.card_id, result }).catch(() => {});
  }, [card]);

  /** 滑动评分：右=秒答、左=忘了、上=吃力（只在翻面后生效） */
  function swipeDir(dx: number, dy: number): "秒答" | "忘了" | "吃力" | null {
    const TH = 64;
    if (Math.abs(dx) > TH && Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "秒答" : "忘了";
    if (dy < -TH && Math.abs(dy) > Math.abs(dx)) return "吃力";
    return null;
  }

  function onPointerDown(e: React.PointerEvent) {
    if (!flipped) return;
    dragRef.current = { x: e.clientX, y: e.clientY, active: true, moved: false };
    setSwipe(null);
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (!d.active) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (Math.hypot(dx, dy) > 10) d.moved = true;
    const dir = swipeDir(dx, dy);
    if (dir && !swipe) {
      try { navigator.vibrate?.(15); } catch { /* 忽略 */ }
    }
    setSwipe(dir ? { dx: Math.max(-90, Math.min(90, dx)), dy: Math.max(-70, Math.min(0, dy)), label: dir } : { dx: dx * 0.35, dy: dy * 0.35, label: "" });
  }

  function onPointerUp() {
    const d = dragRef.current;
    if (!d.active) return;
    d.active = false;
    const dir = swipe?.label;
    setSwipe(null);
    if (dir) {
      try { navigator.vibrate?.(20); } catch { /* 忽略 */ }
      grade(dir);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!card) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.code === "Space") {
        e.preventDefault();
        setFlipped((f) => !f);
      } else if (flipped && (e.key === "1" || e.key === "2" || e.key === "3")) {
        e.preventDefault();
        grade(GRADES[Number(e.key) - 1]);
      } else if (e.key === "ArrowRight" && !flipped) {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, cards.length));
      } else if (e.key === "ArrowLeft" && !flipped) {
        e.preventDefault();
        setIndex((i) => Math.max(0, i - 1));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, flipped, grade, cards.length]);

  if (loading) return <div className="empty">正在取卡…</div>;

  if (!cards.length) {
    return (
      <div className="memo-done">
        <h2>这个范围没有待复习的卡片</h2>
        <p>{scopeLabel(scope, chapterNames)} · 全部卡都到期之外了</p>
        <div className="row">
          <button className="btn primary" onClick={() => setPickerOpen(true)}>换个范围</button>
          <button className="btn" onClick={() => load(scope)}>重新拉取</button>
        </div>
        <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
      </div>
    );
  }

  if (index >= cards.length) {
    const counts = grades.reduce<Record<string, number>>((m, g) => {
      m[g] = (m[g] ?? 0) + 1;
      return m;
    }, {});
    return (
      <div className="memo-done">
        <h2>本批完成</h2>
        <p>
          {cards.length} 张已过完：{Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(" · ") || "未评分"}
          {remaining > 0 ? ` · 本范围还有 ${remaining} 张` : ""}
        </p>
        <div className="row">
          <button className="btn primary" onClick={() => load(scope)}>再拉一批</button>
          <button className="btn" onClick={() => { setIndex(0); setFlipped(false); setGrades([]); }}>重看本批</button>
          <button className="btn" onClick={() => setPickerOpen(true)}>换个范围</button>
        </div>
        <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
      </div>
    );
  }

  const studyHref = `/study?view=study&sid=${card.subject_id ?? sid}&pid=${card.point_id}`;

  return (
    <div className="memo-wrap">
      <div className="stepper-bar">
        <button className="badge-btn" onClick={() => setPickerOpen(true)}>
          范围：{scopeLabel(scope, chapterNames)}
        </button>
        <button className="badge-btn" onClick={() => setFavOpen(true)}>收藏</button>
        <div className="progress-bar"><i style={{ width: `${((index + 1) / cards.length) * 100}%` }} /></div>
        <span className="muted" style={{ fontSize: 12 }}>{index + 1} / {cards.length}</span>
      </div>

      <div
        className={`flip-card${flipped ? " flipped" : ""} clickable${swipe ? " dragging" : ""}`}
        style={swipe ? { transform: `translate(${swipe.dx}px, ${swipe.dy}px)` } : undefined}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => { dragRef.current.active = false; setSwipe(null); }}
        onClick={(e) => {
          const el = e.target as HTMLElement;
          if (el.closest("button, a, input, summary, .options")) return;
          if (dragRef.current.moved) { dragRef.current.moved = false; return; }
          setFlipped((f) => !f);
        }}
        role="button"
        tabIndex={0}
        aria-label={flipped ? "点击返回题目" : "点击翻面看答案"}
        onKeyDown={(e) => { if (e.key === "Enter") setFlipped((f) => !f); }}
      >
        <div className="flip-inner">
          <div className="flip-front">
            <div className="flip-body">
              <div className="card-top">
                <PriorityBadge priority={card.priority} />
                {uniqueLabels([card.kind], [card.card_type]).map((b) => (
                  <span className="badge" key={b}>{b}</span>
                ))}
                {card.new && <span className="badge type">新</span>}
                <span className="spacer" />
                <StarButton kind="card" id={card.card_id} title={card.question} />
                <Link className="study-entry-btn" href={studyHref}
                  title="打开这个知识点的完整讲解">去学</Link>
                <button className="ai-entry-btn" onClick={() => ai.open({
                  point_id: card.point_id,
                  card_id: card.card_id,
                  title: card.title ?? "",
                  question: `这道题我没看懂：${card.question}`,
                })}>问 AI</button>
              </div>
              {isCloze ? (
                <ClozeFace key={card.card_id} card={card} side="front" />
              ) : wordPayload ? (
                <WordFace card={card} side="front" />
              ) : (
                <>
                  <div className="question">{card.question}</div>
                  {card.options.length > 0 && (
                    <div className="options">
                      {card.options.map((o, i) => (
                        <div className="option" key={i}>
                          <span className="letter">{String.fromCharCode(65 + i)}</span>
                          <span>{o.replace(/^[A-D][.、]\s*/, "")}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
              <CardMeta reviews={card.reviews} lastResult={card.last_result}
                lapses={card.lapses} dueAt={card.due_at}
                listenCount={card.listen_count}
                trailing={<span className="muted">{card.title}</span>} />
            </div>
            <button className="btn primary flip-btn" onClick={() => setFlipped(true)}>翻面看答案</button>
          </div>

          <div className="flip-back">
            <div className="flip-body">
              <div className="card-top">
                {uniqueLabels([card.kind], [card.card_type]).map((b) => (
                  <span className="badge" key={b}>{b}</span>
                ))}
                <span className="spacer" />
                <Link className="study-entry-btn" href={studyHref}
                  title="打开这个知识点的完整讲解">去学</Link>
                <button className="ai-entry-btn" onClick={() => ai.open({
                  point_id: card.point_id,
                  card_id: card.card_id,
                  title: card.title ?? "",
                  question: `这道题我没看懂：${card.question}`,
                })}>问 AI</button>
              </div>
              {isCloze ? (
                <ClozeFace key={card.card_id} card={card} side="back" />
              ) : wordPayload ? (
                <WordFace card={card} side="back" />
              ) : (
                <>
                  <div className="question">{card.question}</div>
                  {card.answer_points.length > 0 && (
                    <div className="block answer">
                      <h4>要点</h4>
                      <ul className="answer-points">
                        {card.answer_points.map((a) => <li key={a}>{a}</li>)}
                      </ul>
                    </div>
                  )}
                  <div className="block analysis">
                    <h4>答案</h4>
                    <div className="prose" dangerouslySetInnerHTML={{ __html: answerHtml(card.answer) }} />
                  </div>
                  {card.analysis && (
                    <div className="block analysis">
                      <h4>解析</h4>
                      <div className="prose">{card.analysis}</div>
                    </div>
                  )}
                </>
              )}
              <CardMeta reviews={card.reviews} lastResult={card.last_result}
                lapses={card.lapses} dueAt={card.due_at}
                listenCount={card.listen_count}
                trailing={<span className="muted">{card.title}</span>} />
            </div>
            <button className="btn flip-btn" onClick={() => setFlipped(false)}>返回题目</button>
          </div>
        </div>
      </div>

      {swipe?.label && (
        <div className={`swipe-hint sw-${swipe.label === "秒答" ? "good" : swipe.label === "忘了" ? "bad" : "fuzzy"}`}>
          {swipe.label}
        </div>
      )}

      <div className={`grade-row${flipped ? " show" : ""}`}>
        {GRADES.map((g) => (
          <button key={g} data-grade={g} onClick={() => grade(g)} disabled={!flipped}>{g}</button>
        ))}
      </div>

      <div className="stepper-nav">
        <button className="btn" onClick={() => { setFlipped(false); setIndex((i) => Math.max(0, i - 1)); }}
          disabled={index === 0}>上一张</button>
        <span className="muted" style={{ fontSize: 12 }}>空格翻面 · 1/2/3 或滑动评分</span>
        <button className="btn" onClick={() => { setFlipped(false); setIndex((i) => i + 1); }}>下一张</button>
      </div>

      <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
        onClose={() => setPickerOpen(false)} onApply={applyScope} />
      <FavoritesPanel open={favOpen} sid={sid} onClose={() => setFavOpen(false)} />
    </div>
  );
}

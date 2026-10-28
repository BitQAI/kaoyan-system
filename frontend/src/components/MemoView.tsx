"use client";
import { useCallback, useEffect, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { answerHtml } from "@/lib/render";
import type { Card } from "@/lib/types";
import { useAi } from "./AiProvider";

const GRADES = ["秒答", "吃力", "忘了"] as const;

export default function MemoView({ sid }: { sid: string }) {
  const [cards, setCards] = useState<Card[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [grades, setGrades] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const ai = useAi();

  const load = useCallback(() => {
    setLoading(true);
    getJson<{ items: Card[] }>(`/api/queue/today?mode=memo&sid=${sid}&limit=20`)
      .then((d) => {
        setCards(d.items);
        setIndex(0);
        setFlipped(false);
        setGrades([]);
      })
      .catch(() => setCards([]))
      .finally(() => setLoading(false));
  }, [sid]);

  useEffect(() => { load(); }, [load]);

  const card = cards[index];

  const grade = useCallback((result: string) => {
    if (!card) return;
    setGrades((g) => [...g, result]);
    setFlipped(false);
    setIndex((i) => i + 1);
    void postJson("/api/progress/card", { card_id: card.card_id, result }).catch(() => {});
  }, [card]);

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
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, flipped, grade]);

  if (loading) return <div className="empty">正在取卡…</div>;
  if (!cards.length) return <div className="empty">这一科没有待复习的卡片。</div>;

  if (index >= cards.length) {
    const counts = grades.reduce<Record<string, number>>((m, g) => {
      m[g] = (m[g] ?? 0) + 1;
      return m;
    }, {});
    return (
      <div className="memo-done">
        <h2>本组完成</h2>
        <p>{cards.length} 张已过完：{Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(" · ") || "未评分"}</p>
        <div className="row">
          <button className="btn primary" onClick={load}>再来一组</button>
          <button className="btn" onClick={() => { setIndex(0); setFlipped(false); setGrades([]); }}>重看本组</button>
        </div>
      </div>
    );
  }

  return (
    <div className="memo-wrap">
      <div className="memo-progress">
        <span>{index + 1} / {cards.length}</span>
        <span className="bar"><i style={{ width: `${(index / cards.length) * 100}%` }} /></span>
        <button className="badge-btn" onClick={load}>换一组</button>
      </div>

      <div className={`flip-card${flipped ? " flipped" : ""}`}>
        <div className="flip-inner">
          <div className="flip-front">
            <div className="flip-body">
              <div className="card-top">
                <span className="badge kind">{card.kind}</span>
                <span className="badge">{card.card_type}</span>
                {card.new && <span className="badge type">新</span>}
                <span className="spacer" />
                <button className="ai-entry-btn" onClick={() => ai.open({
                  point_id: card.point_id,
                  title: card.title ?? "",
                  question: `这道题我没看懂：${card.question}`,
                })}>问 AI</button>
              </div>
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
              <div className="card-foot">
                <span>{card.title}</span>
                <span>空格翻面</span>
              </div>
            </div>
            <button className="btn primary flip-btn" onClick={() => setFlipped(true)}>翻面看答案</button>
          </div>

          <div className="flip-back">
            <div className="flip-body">
              <div className="card-top">
                <span className="badge kind">{card.kind}</span>
                <span className="badge">{card.card_type}</span>
              </div>
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
            </div>
            <button className="btn flip-btn" onClick={() => setFlipped(false)}>返回题目</button>
          </div>
        </div>
      </div>

      <div className={`grade-row${flipped ? " show" : ""}`}>
        {GRADES.map((g) => (
          <button key={g} data-grade={g} onClick={() => grade(g)} disabled={!flipped}>{g}</button>
        ))}
      </div>
      <p className="memo-hint">空格翻面 · 1 秒答 · 2 吃力 · 3 忘了</p>
    </div>
  );
}

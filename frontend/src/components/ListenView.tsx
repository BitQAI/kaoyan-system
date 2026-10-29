"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { paragraphs, splitScript } from "@/lib/render";
import { DEFAULT_SCOPE, readScope, scopeLabel, writeScope, type Scope } from "@/lib/scope";
import type { Chapter, ListenItem } from "@/lib/types";
import { useAi } from "./AiProvider";
import RangePicker from "./RangePicker";

const RATES = [0.75, 0.95, 1.25];

export default function ListenView({ sid, chapters }: { sid: string; chapters: Chapter[] }) {
  const [items, setItems] = useState<ListenItem[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [rate, setRate] = useState(0.95);
  const [supported, setSupported] = useState(true);
  const [showAnswer, setShowAnswer] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const activeRef = useRef<string | null>(null);
  const ai = useAi();

  const chapterNames: Record<string, string> = {};
  chapters.forEach((c) => { chapterNames[c.id] = c.name; });

  const load = useCallback((next: Scope, keepIdx = false) => {
    setLoading(true);
    setSpeaking(false);
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    activeRef.current = null;
    postJson<{ items: ListenItem[]; remaining: number }>("/api/queue/custom", {
      mode: "listen", subjects: [sid], chapters: next.chapters, limit: next.limit,
    })
      .then((d) => {
        setItems(d.items);
        setRemaining(d.remaining);
        if (!keepIdx) setIdx(0);
      })
      .catch(() => { setItems([]); setRemaining(0); })
      .finally(() => setLoading(false));
  }, [sid]);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    const saved = readScope(sid);
    setScope(saved);
    load(saved);
    return () => { if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel(); };
  }, [sid, load]);

  function applyScope(next: Scope) {
    setScope(next);
    writeScope(sid, next);
    setPickerOpen(false);
    setShowAnswer(false);
    load(next);
  }

  const item = items[idx];

  function stop() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    activeRef.current = null;
    setSpeaking(false);
  }

  function speak(target: ListenItem) {
    if (!("speechSynthesis" in window)) return;
    stop();
    const parts = splitScript(target.script);
    // 只念设问与解析：不给答案，听的时候先自己想
    const text = [parts.ask && `设问：${parts.ask}`,
                  parts.analysis && `解析：${parts.analysis}`,
                  parts.rest].filter(Boolean).join("。");
    if (!text) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "zh-CN";
    utter.rate = rate;
    utter.pitch = 1;
    utter.onend = () => {
      if (activeRef.current !== target.point_id) return;
      activeRef.current = null;
      setSpeaking(false);
      void postJson("/api/progress/listen", { point_id: target.point_id }).catch(() => {});
      setItems((list) => list.map((x) => x.point_id === target.point_id
        ? { ...x, heard: true, listen_count: x.listen_count + 1 } : x));
    };
    utter.onerror = () => { if (activeRef.current === target.point_id) stop(); };
    activeRef.current = target.point_id;
    setSpeaking(true);
    window.speechSynthesis.speak(utter);
  }

  function step(delta: number) {
    stop();
    setShowAnswer(false);
    const next = idx + delta;
    if (next < 0) return;
    if (next >= items.length) { setIdx(items.length); return; }
    setIdx(next);
  }

  if (!supported) {
    return <div className="empty">当前浏览器不支持语音合成。朗读稿仍可阅读。</div>;
  }
  if (loading) return <div className="empty">正在取听学队列…</div>;

  if (!items.length) {
    return (
      <div className="memo-done">
        <h2>这个范围听完了</h2>
        <p>{scopeLabel(scope, chapterNames)} · 共 {scope.limit} 条一批</p>
        <div className="row">
          <button className="btn primary" onClick={() => setPickerOpen(true)}>换个范围</button>
          <button className="btn" onClick={() => load(scope)}>再拉一批</button>
        </div>
        <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
      </div>
    );
  }

  if (idx >= items.length) {
    return (
      <div className="memo-done">
        <h2>本批听完</h2>
        <p>{items.length} 条 · 本范围剩余 {remaining} 条</p>
        <div className="row">
          <button className="btn primary" onClick={() => load(scope)}>再拉一批</button>
          <button className="btn" onClick={() => { setIdx(0); }}>重听本批</button>
          <button className="btn" onClick={() => setPickerOpen(true)}>换个范围</button>
        </div>
        <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
      </div>
    );
  }

  const parts = splitScript(item.script);

  return (
    <>
      <div className="stepper-bar">
        <button className="badge-btn" onClick={() => setPickerOpen(true)}>
          范围：{scopeLabel(scope, chapterNames)}
        </button>
        <div className="progress-bar"><i style={{ width: `${((idx + 1) / items.length) * 100}%` }} /></div>
        <span className="muted" style={{ fontSize: 12 }}>{idx + 1} / {items.length}</span>
      </div>

      <article className="q-card stepper-card">
        <div className="card-top">
          <span className="badge kind">{item.kind ?? "朗读"}</span>
          {item.exam_types.map((t) => <span className="badge" key={t}>{t}</span>)}
          {item.heard && <span className="badge">听过 {item.listen_count} 次</span>}
          <span className="spacer" />
          <button className="ai-entry-btn" onClick={() => ai.open({
            point_id: item.point_id,
            card_id: item.card_id ?? undefined,
            title: item.title,
            question: `这题我没听懂：${item.question ?? item.point}`,
          })}>问 AI</button>
        </div>

        <h2 className="study-title">{item.title}</h2>

        <section className="listen-block">
          <h3>设问</h3>
          <div className="prose" dangerouslySetInnerHTML={{ __html: paragraphs(parts.ask || item.question || item.point) }} />
        </section>

        <section className="listen-block">
          <h3>解析</h3>
          <div className="prose" dangerouslySetInnerHTML={{ __html: paragraphs(parts.analysis) }} />
        </section>

        {parts.answer && (
          <div style={{ marginTop: 10 }}>
            <button className="badge-btn" onClick={() => setShowAnswer((s) => !s)}>
              {showAnswer ? "收起答案" : "看答案（不会朗读）"}
            </button>
            {showAnswer && (
              <div className="prose" style={{ marginTop: 8 }}
                dangerouslySetInnerHTML={{ __html: paragraphs(parts.answer) }} />
            )}
          </div>
        )}

        <div className="listen-actions">
          <button className="btn primary" onClick={() => speak(item)} disabled={speaking}>
            {speaking ? "朗读中…" : "朗读设问与解析"}
          </button>
          <button className="btn" onClick={stop} disabled={!speaking}>停止</button>
          <div className="rate-select">
            {RATES.map((r) => (
              <button key={r} className={rate === r ? "on" : ""} onClick={() => setRate(r)}>{r}×</button>
            ))}
          </div>
        </div>
        {speaking && <div className="wave">{[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <i key={i} />)}</div>}

        <div className="stepper-nav">
          <button className="btn" onClick={() => step(-1)} disabled={idx === 0}>上一条</button>
          <span className="muted" style={{ fontSize: 12 }}>{item.chapter_name}</span>
          <button className="btn primary" onClick={() => step(1)}>下一条</button>
        </div>
      </article>

      <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
        onClose={() => setPickerOpen(false)} onApply={applyScope} />
    </>
  );
}

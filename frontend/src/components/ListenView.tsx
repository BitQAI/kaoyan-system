"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { postJson } from "@/lib/api";
import { answerHtml, paragraphs } from "@/lib/render";
import { DEFAULT_SCOPE, readScope, scopeLabel, writeScope, type Scope } from "@/lib/scope";
import type { Chapter, ListenItem } from "@/lib/types";
import { useAi } from "./AiProvider";
import { PriorityBadge, StarButton, uniqueLabels } from "./Badges";
import CardMeta from "./CardMeta";
import FavoritesPanel from "./FavoritesPanel";
import RangePicker from "./RangePicker";

const RATE_MIN = 0.6;
const RATE_MAX = 1.6;
const RATE_STEP = 0.05;

export default function ListenView({ sid, chapters }: { sid: string; chapters: Chapter[] }) {
  const [items, setItems] = useState<ListenItem[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [rate, setRate] = useState(0.95);
  const [supported, setSupported] = useState(true);
  const [showNotes, setShowNotes] = useState(false);
  const [autoPlay, setAutoPlay] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [favOpen, setFavOpen] = useState(false);
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const activeRef = useRef<string | null>(null);
  const autoRef = useRef(true);
  const timerRef = useRef<number | null>(null);

  useEffect(() => { autoRef.current = autoPlay; }, [autoPlay]);
  const ai = useAi();

  const chapterNames: Record<string, string> = {};
  chapters.forEach((c) => { chapterNames[c.id] = c.name; });

  const load = useCallback((next: Scope) => {
    setLoading(true);
    setSpeaking(false);
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    activeRef.current = null;
    postJson<{ items: ListenItem[]; remaining: number }>("/api/queue/custom", {
      mode: "listen", subjects: [sid], chapters: next.chapters, limit: next.limit,
    })
      .then((d) => { setItems(d.items); setRemaining(d.remaining); setIdx(0); })
      .catch(() => { setItems([]); setRemaining(0); })
      .finally(() => setLoading(false));
  }, [sid]);

  // 语音引擎预热：首次朗读常要等音色加载，先空跑一次
  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.getVoices();
    try {
      const warm = new SpeechSynthesisUtterance(" ");
      warm.volume = 0;
      window.speechSynthesis.speak(warm);
      window.speechSynthesis.cancel();
    } catch { /* 忽略 */ }
  }, []);

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
    load(next);
  }

  const item = items[idx];

  // 锁屏 / 耳机控制：把当前朗读登记成系统媒体会话
  useEffect(() => {
    const ms = (navigator as unknown as { mediaSession?: any }).mediaSession;
    if (!ms || !item) return;
    try {
      const MM = (window as unknown as { MediaMetadata?: any }).MediaMetadata;
      if (MM) {
        ms.metadata = new MM({
          title: item.title,
          artist: item.chapter_name,
          album: "考研听学",
        });
      }
    } catch { /* 老浏览器忽略 */ }
  }, [item]);

  useEffect(() => {
    const ms = (navigator as unknown as { mediaSession?: any }).mediaSession;
    if (!ms) return;
    const set = (k: string, fn: (() => void) | null) => {
      try { ms.setActionHandler(k, fn); } catch { /* 不支持的动作忽略 */ }
    };
    set("play", () => { if (item) speak(item); });
    set("pause", () => stop());
    set("previoustrack", () => step(-1));
    set("nexttrack", () => step(1));
    return () => {
      ["play", "pause", "previoustrack", "nexttrack"].forEach((k) => set(k, null));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.card_id, items.length]);

  // 从后台切回时，若仍处于朗读状态就尝试续播（iOS 仍可能被系统停掉）
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === "visible" && speaking) {
        try { window.speechSynthesis.resume(); } catch { /* 忽略 */ }
      }
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [speaking]);

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function stop() {
    clearTimer();
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    activeRef.current = null;
    setSpeaking(false);
  }

  function speak(target: ListenItem) {
    if (!("speechSynthesis" in window)) return;
    stop();
    // 只念考点与作答：评分要点不念，留着自己看
    const text = [target.question, target.answer || target.analysis || target.fallback]
      .filter(Boolean).join("。");
    if (!text) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "zh-CN";
    utter.rate = rate;
    utter.pitch = 1;
    utter.onend = () => {
      if (activeRef.current !== target.card_id) return;
      activeRef.current = null;
      setSpeaking(false);
      void postJson("/api/progress/listen", { card_id: target.card_id }).catch(() => {});
      setItems((list) => list.map((x) => x.card_id === target.card_id
        ? { ...x, heard: true, listen_count: x.listen_count + 1 } : x));

      // 连播：停一拍后自动翻到下一条并朗读；到末尾就停在本批完成页
      const i = items.findIndex((x) => x.card_id === target.card_id);
      const next = items[i + 1];
      if (!autoRef.current || !next) {
        if (!next) setIdx(items.length);
        return;
      }
      timerRef.current = window.setTimeout(() => {
        setIdx(i + 1);
        speak(next);
      }, 800);
    };
    utter.onerror = () => { if (activeRef.current === target.card_id) stop(); };
    activeRef.current = target.card_id;
    setSpeaking(true);
    window.speechSynthesis.speak(utter);
  }

  function step(delta: number) {
    stop();
    const next = idx + delta;
    if (next < 0) return;
    if (next >= items.length) { setIdx(items.length); return; }
    setIdx(next);
  }

  if (!supported) {
    return <div className="empty">当前浏览器不支持语音合成，考点与解析仍可阅读。</div>;
  }
  if (loading) return <div className="empty">正在取听学队列…</div>;

  if (!items.length) {
    return (
      <div className="memo-done">
        <h2>这个范围听完了</h2>
        <p>{scopeLabel(scope, chapterNames)}</p>
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
          <button className="btn" onClick={() => setIdx(0)}>重听本批</button>
          <button className="btn" onClick={() => setPickerOpen(true)}>换个范围</button>
        </div>
        <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
      </div>
    );
  }

  const badges = uniqueLabels([item.kind], [item.card_type], item.exam_types ?? []);

  return (
    <>
      <div className="stepper-bar">
        <button className="badge-btn" onClick={() => setPickerOpen(true)}>
          范围：{scopeLabel(scope, chapterNames)}
        </button>
        <button className="badge-btn" onClick={() => setFavOpen(true)}>收藏</button>
        <div className="progress-bar"><i style={{ width: `${((idx + 1) / items.length) * 100}%` }} /></div>
        <span className="muted" style={{ fontSize: 12 }}>{idx + 1} / {items.length}</span>
      </div>

      <article className="q-card stepper-card">
        <div className="card-top">
          <PriorityBadge priority={item.priority} />
          {badges.map((b) => <span className="badge" key={b}>{b}</span>)}
          <span className="spacer" />
          <StarButton kind="card" id={item.card_id} title={item.question} />
          <button className="ai-entry-btn" onClick={() => ai.open({
            point_id: item.point_id,
            card_id: item.card_id,
            title: item.title,
            question: `这条我没听懂：${item.question}`,
          })}>问 AI</button>
        </div>

        <h2 className="study-title">{item.title}</h2>

        <section className="listen-block">
          <h3>考点</h3>
          <div className="prose" dangerouslySetInnerHTML={{ __html: paragraphs(item.question) }} />
        </section>

        <section className="listen-block">
          <h3>这样作答</h3>
          <div className="prose"
            dangerouslySetInnerHTML={{ __html: answerHtml(item.answer || item.fallback) }} />
        </section>

        {item.analysis && (
          <div className="listen-notes">
            <button className="badge-btn" onClick={() => setShowNotes((v) => !v)}>
              {showNotes ? "收起评分要点" : "评分要点（不朗读）"}
            </button>
            {showNotes && (
              <div className="prose" style={{ marginTop: 8 }}
                dangerouslySetInnerHTML={{ __html: paragraphs(item.analysis) }} />
            )}
          </div>
        )}

        <div className="listen-actions">
          <button className="btn primary" onClick={() => speak(item)} disabled={speaking}>
            {speaking ? "朗读中…" : "朗读考点与作答"}
          </button>
          <button className="btn" onClick={stop} disabled={!speaking}>停止</button>
          <button className={`btn${autoPlay ? " primary" : ""}`}
            onClick={() => setAutoPlay((v) => !v)}
            title="朗读完一条后自动播下一条">
            {autoPlay ? "连播中" : "单条"}
          </button>
          <label className="rate-slider">
            <span className="muted" style={{ fontSize: 11.5 }}>语速</span>
            <input
              type="range" min={RATE_MIN} max={RATE_MAX} step={RATE_STEP}
              value={rate}
              onChange={(e) => setRate(Number(e.target.value))}
              aria-label="朗读语速"
            />
            <span className="rate-value">{rate.toFixed(2)}×</span>
          </label>
        </div>
        {speaking && <div className="wave">{[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <i key={i} />)}</div>}

        <CardMeta reviews={item.reviews} lastResult={item.last_result}
          lapses={item.lapses} dueAt={item.due_at} listenCount={item.listen_count}
          trailing={<span className="muted">{item.chapter_name}</span>} />

        <div className="stepper-nav">
          <button className="btn" onClick={() => step(-1)} disabled={idx === 0}>上一条</button>
          <span className="muted" style={{ fontSize: 12 }}>{item.chapter_name}</span>
          <button className="btn primary" onClick={() => step(1)}>下一条</button>
        </div>
      </article>

      <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
        onClose={() => setPickerOpen(false)} onApply={applyScope} />
      <FavoritesPanel open={favOpen} sid={sid} onClose={() => setFavOpen(false)} />
    </>
  );
}

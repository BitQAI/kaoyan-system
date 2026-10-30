"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { postJson } from "@/lib/api";
import { loadAudio, loadClip, pinAudio, readRate, RATE_DEFAULT } from "@/lib/listen";
import {
  GAPS, MODES, REPEATS, readGap, readMode, readRepeat,
  segmentsFor, wordPayloadOf, writeSetting, type ListenMode,
} from "@/lib/listen-player";
import { answerHtml, paragraphs } from "@/lib/render";
import { clearResume, readResume, saveResume } from "@/lib/resume";
import { DEFAULT_SCOPE, readScope, scopeLabel, writeScope, type Scope } from "@/lib/scope";
import type { Chapter, ListenItem } from "@/lib/types";
import { useAi } from "./AiProvider";
import { PriorityBadge, StarButton, uniqueLabels } from "./Badges";
import CardMeta from "./CardMeta";
import FavoritesPanel from "./FavoritesPanel";
import RangePicker from "./RangePicker";
import { Quote } from "./WordFace";

function clock(sec: number): string {
  const total = Number.isFinite(sec) ? Math.max(0, Math.floor(sec)) : 0;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export default function ListenView({ sid, chapters }: { sid: string; chapters: Chapter[] }) {
  const [items, setItems] = useState<ListenItem[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [rate, setRate] = useState(RATE_DEFAULT);
  const [pos, setPos] = useState(0);
  const [dur, setDur] = useState(0);
  const [showNotes, setShowNotes] = useState(false);
  const [autoPlay, setAutoPlay] = useState(true);
  const [mode, setMode] = useState<ListenMode>("wms");
  const [repeat, setRepeat] = useState(1);
  const [gap, setGap] = useState(1);
  const [segIdx, setSegIdx] = useState(0);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [favOpen, setFavOpen] = useState(false);
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const activeRef = useRef<string | null>(null);
  const autoRef = useRef(true);
  const timerRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const ttsRef = useRef(false);
  const seqRef = useRef(0);

  const item = items[idx];
  const wordPayload = wordPayloadOf(item);
  const segments = item ? segmentsFor(item, mode) : [];
  const st = useRef({ items, idx, segIdx, repeat, gap, mode, speaking });
  st.current = { items, idx, segIdx, repeat, gap, mode, speaking };

  useEffect(() => { autoRef.current = autoPlay; }, [autoPlay]);
  const ai = useAi();

  const chapterNames: Record<string, string> = {};
  chapters.forEach((c) => { chapterNames[c.id] = c.name; });

  const load = useCallback((next: Scope, resume = false) => {
    setLoading(true);
    setSpeaking(false);
    setPaused(false);
    seqRef.current += 1;
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    audioRef.current?.pause();
    activeRef.current = null;
    postJson<{ items: ListenItem[]; remaining: number }>("/api/queue/custom", {
      mode: "listen", subjects: [sid], chapters: next.chapters, limit: next.limit,
    })
      .then((d) => {
        let start = 0;
        if (resume) {
          const cardId = readResume("listen", sid);
          const i = cardId ? d.items.findIndex((x) => x.card_id === cardId) : -1;
          if (i > 0) start = i;
        }
        setItems(d.items);
        setRemaining(d.remaining);
        setIdx(start);
        setSegIdx(0);
      })
      .catch(() => { setItems([]); setRemaining(0); })
      .finally(() => setLoading(false));
  }, [sid]);

  useEffect(() => {
    if (!items.length) return;
    const current = items[idx];
    if (current) saveResume("listen", sid, current.card_id);
    else clearResume("listen", sid);
  }, [items, idx, sid]);

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

  // 语速在「我的 → 账号」设置；本页与那边同路由，不会重新挂载
  useEffect(() => {
    const sync = () => setRate(readRate());
    sync();
    window.addEventListener("focus", sync);
    window.addEventListener("storage", sync);
    document.addEventListener("visibilitychange", sync);
    document.addEventListener("pointerdown", sync);
    return () => {
      window.removeEventListener("focus", sync);
      window.removeEventListener("storage", sync);
      document.removeEventListener("visibilitychange", sync);
      document.removeEventListener("pointerdown", sync);
    };
  }, []);

  // 听法/遍数/间隔：跨会话记住
  useEffect(() => {
    setMode(readMode());
    setRepeat(readRepeat());
    setGap(readGap());
  }, []);

  // 播放器单例：<audio> 播 blob，锁屏/切后台不会被系统掐断
  useEffect(() => {
    const a = new Audio();
    a.preload = "auto";
    audioRef.current = a;
    return () => {
      a.pause();
      a.removeAttribute("src");
      audioRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = rate;
  }, [rate]);

  useEffect(() => {
    const saved = readScope(sid);
    setScope(saved);
    load(saved, true);
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, [sid, load]);

  function applyScope(next: Scope) {
    setScope(next);
    writeScope(sid, next);
    setPickerOpen(false);
    load(next);
  }

  function applyMode(next: ListenMode) {
    setMode(next);
    writeSetting("mode", next);
    setSegIdx(0);
    if (st.current.speaking) void playFrom(st.current.idx, 0, st.current.repeat);
  }

  function applyRepeat(next: number) {
    setRepeat(next);
    writeSetting("repeat", next);
  }

  function applyGap(next: number) {
    setGap(next);
    writeSetting("gap", next);
  }

  // 锁屏 / 耳机控制：把当前朗读登记成系统媒体会话
  useEffect(() => {
    const ms = (navigator as unknown as { mediaSession?: any }).mediaSession;
    if (!ms || !item) return;
    try {
      const MM = (window as unknown as { MediaMetadata?: any }).MediaMetadata;
      if (MM) {
        ms.metadata = new MM({
          title: wordPayload?.word ?? item.title,
          artist: item.chapter_name,
          album: "考研听学",
        });
      }
    } catch { /* 老浏览器忽略 */ }
  }, [item, wordPayload]);

  useEffect(() => {
    const ms = (navigator as unknown as { mediaSession?: any }).mediaSession;
    if (!ms) return;
    const set = (k: string, fn: (() => void) | null) => {
      try { ms.setActionHandler(k, fn); } catch { /* 不支持的动作忽略 */ }
    };
    set("play", () => void resume());
    set("pause", pause);
    set("previoustrack", () => gotoCard(-1));
    set("nexttrack", () => gotoCard(1));
    set("seekbackward", () => gotoSegment(-1));
    set("seekforward", () => gotoSegment(1));
    return () => {
      ["play", "pause", "previoustrack", "nexttrack", "seekbackward", "seekforward"]
        .forEach((k) => set(k, null));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);

  // 从后台切回时，TTS 回退态尝试续播（音频态由系统自行恢复）
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === "visible" && speaking && ttsRef.current) {
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

  /** 只停声音与定时器，不改变“这一条还在播”的界面状态 */
  function detach() {
    clearTimer();
    ttsRef.current = false;
    seqRef.current += 1;
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    const a = audioRef.current;
    if (a) {
      a.onended = null;
      a.onerror = null;
      a.ontimeupdate = null;
      a.onloadedmetadata = null;
      a.pause();
    }
    setPos(0);
    setDur(0);
  }

  function pause() {
    clearTimer();
    audioRef.current?.pause();
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.pause();
    setPaused(true);
  }

  async function resume() {
    const a = audioRef.current;
    if (a && a.src) {
      try { await a.play(); setPaused(false); return; } catch { /* 落到 TTS */ }
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.resume();
    }
    setPaused(false);
  }

  function stop() {
    detach();
    activeRef.current = null;
    setSpeaking(false);
    setPaused(false);
  }

  /** 播一段；seg 越界时进入下一遍或结束本卡 */
  async function playSegment(cardIdx: number, seg: number, left: number) {
    const seq = seqRef.current;
    const list = st.current.items;
    const target = list[cardIdx];
    if (!target) { stop(); setIdx(list.length); return; }
    if (activeRef.current !== target.card_id) activeRef.current = target.card_id;

    const segs = segmentsFor(target, st.current.mode);
    if (seg >= segs.length) {
      if (left > 1) { await playSegment(cardIdx, 0, left - 1); return; }
      finishCard(cardIdx);
      return;
    }

    const cur = segs[seg];
    setSegIdx(seg);
    let url: string;
    try {
      url = cur.clip
        ? await loadClip(target.card_id, cur.clip)
        : await loadAudio(target.card_id);
    } catch {
      if (cur.clip) { void playSegment(cardIdx, seg + 1, left); return; }
      speak(target);
      return;
    }
    if (seq !== seqRef.current) return;   // 期间切了内容
    const a = audioRef.current;
    if (!a) return;

    a.src = url;
    a.playbackRate = readRate();
    a.onended = () => void playSegment(cardIdx, seg + 1, left);
    a.onerror = () => {
      if (cur.clip) void playSegment(cardIdx, seg + 1, left);
      else speak(target);
    };
    a.onloadedmetadata = () => setDur(Number.isFinite(a.duration) ? a.duration : 0);
    a.ontimeupdate = () => setPos(a.currentTime);
    try {
      await a.play();
      setPaused(false);
    } catch { /* 自动播放被拦，等用户点 */ }

    const prefetch = segs[seg + 1];
    if (prefetch) {
      const task = prefetch.clip
        ? loadClip(target.card_id, prefetch.clip)
        : loadAudio(target.card_id);
      void task.catch(() => {});
    }
  }

  async function playFrom(cardIdx: number, seg: number, left: number) {
    detach();
    const target = st.current.items[cardIdx];
    if (!target) { setIdx(st.current.items.length); return; }
    activeRef.current = target.card_id;
    setSpeaking(true);
    setPaused(false);
    setIdx(cardIdx);
    pinAudio(target.card_id);
    await playSegment(cardIdx, seg, left);
  }

  // 一张卡读完：记账 + 间隔后连播下一张
  function finishCard(cardIdx: number) {
    const target = st.current.items[cardIdx];
    if (!target) return;
    ttsRef.current = false;
    activeRef.current = null;
    setSpeaking(false);
    setPaused(false);
    void postJson("/api/progress/listen", { card_id: target.card_id }).catch(() => {});
    setItems((list) => list.map((x) => x.card_id === target.card_id
      ? { ...x, heard: true, listen_count: x.listen_count + 1 } : x));

    const next = st.current.items[cardIdx + 1];
    if (!autoRef.current || !next) {
      if (!next) setIdx(st.current.items.length);
      return;
    }
    const wait = Math.max(0, st.current.gap) * 1000;
    timerRef.current = window.setTimeout(() => {
      void playFrom(cardIdx + 1, 0, st.current.repeat);
    }, wait);
  }

  // 没有离线音频或加载失败时的兜底：用浏览器语音念当前内容
  function speak(target: ListenItem) {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const p = wordPayloadOf(target);
    const text = p
      ? [p.word, (p.meanings ?? []).map((m) => m.cn).join("，"),
         (p.examples ?? [])[0]?.quote].filter(Boolean).join("。")
      : [target.question, target.answer || target.analysis || target.fallback]
        .filter(Boolean).join("。");
    if (!text) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = p ? "en-US" : "zh-CN";
    utter.rate = readRate();
    utter.onend = () => finishCard(st.current.idx);
    utter.onerror = () => { if (activeRef.current === target.card_id) stop(); };
    ttsRef.current = true;
    activeRef.current = target.card_id;
    setSpeaking(true);
    window.speechSynthesis.speak(utter);
  }

  function gotoCard(delta: number) {
    const s = st.current;
    const next = s.idx + delta;
    if (next < 0) return;
    if (next >= s.items.length) { stop(); setIdx(s.items.length); return; }
    if (s.speaking) void playFrom(next, 0, s.repeat);
    else { setIdx(next); setSegIdx(0); setPaused(false); }
  }

  function gotoSegment(delta: number) {
    const s = st.current;
    const target = s.items[s.idx];
    if (!target) return;
    const segs = segmentsFor(target, s.mode);
    const next = s.segIdx + delta;
    if (next < 0) { gotoCard(-1); return; }
    if (next >= segs.length) { gotoCard(1); return; }
    if (s.speaking) void playFrom(s.idx, next, s.repeat);
    else setSegIdx(next);
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
          <button className="btn" onClick={() => { setIdx(0); setSegIdx(0); }}>重听本批</button>
          <button className="btn" onClick={() => setPickerOpen(true)}>换个范围</button>
        </div>
        <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
          onClose={() => setPickerOpen(false)} onApply={applyScope} />
      </div>
    );
  }

  const badges = uniqueLabels([item.kind], [item.card_type], item.exam_types ?? []);
  const isPlaying = speaking && !paused;

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
          <Link className="study-entry-btn" title="打开这个知识点的完整讲解"
            href={`/study?view=study&sid=${item.subject_id}&pid=${item.point_id}`}>
            去学
          </Link>
          <button className="ai-entry-btn" onClick={() => ai.open({
            point_id: item.point_id,
            card_id: item.card_id,
            title: item.title,
            question: `这条我没听懂：${item.question}`,
          })}>问 AI</button>
        </div>

        <h2 className="study-title">{item.title}</h2>

        {wordPayload && (
          <section className="listen-block listen-word">
            <div className="listen-word-head">
              <span className="word-title">{wordPayload.word}</span>
              {wordPayload.phonetic && (
                <span className="word-phonetic">{wordPayload.phonetic}</span>
              )}
            </div>
            <ul className="word-senses">
              {(wordPayload.meanings ?? []).map((m, i) => (
                <li key={i}><span className="pos">{m.pos}</span>{m.cn}</li>
              ))}
            </ul>
            {(wordPayload.examples ?? []).slice(0, 1).map((ex, i) => (
              <blockquote className={`word-quote${ex.kind === "真题" ? "" : " note"}`} key={i}>
                <Quote text={ex.quote} word={wordPayload.word} />
                {ex.cn && <span className="cn">{ex.cn}</span>}
              </blockquote>
            ))}
            <div className="seg-row" role="group" aria-label="分段重听">
              {segments.map((s, i) => (
                <button
                  key={s.label}
                  className={`seg-chip${speaking && segIdx === i ? " on" : ""}`}
                  onClick={() => void playFrom(idx, i, repeat)}
                >{s.label}</button>
              ))}
            </div>
          </section>
        )}

        <section className="listen-block" hidden={!!wordPayload}>
          <h3>考点</h3>
          <div className="prose" dangerouslySetInnerHTML={{ __html: paragraphs(item.question) }} />
        </section>

        <section className="listen-block" hidden={!!wordPayload}>
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

        <div className="player">
          <div className="transport">
            <button className="tp" onClick={() => gotoCard(-1)} title="上一个词">⏮</button>
            <button className="tp" onClick={() => gotoSegment(-1)} title="上一句">⏪</button>
            <button className="tp main" onClick={() => (speaking ? (paused ? void resume() : pause()) : void playFrom(idx, 0, repeat))}
              title={isPlaying ? "暂停" : "播放"}>
              {isPlaying ? "⏸" : "▶"}
            </button>
            <button className="tp" onClick={() => gotoSegment(1)} title="下一句">⏩</button>
            <button className="tp" onClick={() => gotoCard(1)} title="下一个词">⏭</button>
          </div>
          <div className="player-meta">
            <span className="muted">{speaking ? segments[segIdx]?.label ?? "" : "就绪"}</span>
            <span className="muted">{clock(pos)} / {clock(dur)}</span>
            <button className={`badge-btn${autoPlay ? " on" : ""}`}
              onClick={() => setAutoPlay((v) => !v)}>
              {autoPlay ? "连播" : "单条"}
            </button>
            <span className="muted" title="在「我的 → 账号」调整">语速 {rate.toFixed(2)}×</span>
          </div>
          {dur > 0 && (
            <input className="seek" type="range" min={0} max={dur} step={0.1}
              value={Math.min(pos, dur)} aria-label="播放进度"
              onChange={(e) => {
                const next = Number(e.target.value);
                setPos(next);
                if (audioRef.current) audioRef.current.currentTime = next;
              }} />
          )}
          <div className="player-opts">
            {wordPayload && (
              <>
                <span className="opt-label">听法</span>
                {MODES.map((m) => (
                  <button key={m.id} className={`chip${mode === m.id ? " on" : ""}`}
                    onClick={() => applyMode(m.id)}>{m.label}</button>
                ))}
              </>
            )}
            <span className="opt-label">遍数</span>
            {REPEATS.map((n) => (
              <button key={n} className={`chip${repeat === n ? " on" : ""}`}
                onClick={() => applyRepeat(n)}>{n}</button>
            ))}
            <span className="opt-label">间隔</span>
            {GAPS.map((n) => (
              <button key={n} className={`chip${gap === n ? " on" : ""}`}
                onClick={() => applyGap(n)}>{n}s</button>
            ))}
          </div>
        </div>

        <CardMeta reviews={item.reviews} lastResult={item.last_result}
          lapses={item.lapses} dueAt={item.due_at} listenCount={item.listen_count}
          trailing={<span className="muted">{item.chapter_name}</span>} />
      </article>

      <RangePicker open={pickerOpen} chapters={chapters} scope={scope}
        onClose={() => setPickerOpen(false)} onApply={applyScope} />
      <FavoritesPanel open={favOpen} sid={sid} onClose={() => setFavOpen(false)} />
    </>
  );
}

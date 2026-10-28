"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { esc, scriptHtml } from "@/lib/render";
import type { ListenItem } from "@/lib/types";
import { useAi } from "./AiProvider";

const RATES = [0.75, 0.95, 1.25];

export default function ListenView({ sid }: { sid: string }) {
  const [items, setItems] = useState<ListenItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [rate, setRate] = useState(0.95);
  const [supported, setSupported] = useState(true);
  const activeRef = useRef<string | null>(null);
  const ai = useAi();

  const load = useCallback(() => {
    setLoading(true);
    getJson<{ items: ListenItem[] }>(`/api/queue/today?mode=listen&sid=${sid}&limit=8`)
      .then((d) => setItems(d.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [sid]);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "speechSynthesis" in window);
    load();
    return () => { stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  function stop() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    activeRef.current = null;
    setSpeakingId(null);
  }

  function speak(item: ListenItem) {
    if (!("speechSynthesis" in window)) return;
    stop();
    const utter = new SpeechSynthesisUtterance(item.script);
    utter.lang = "zh-CN";
    utter.rate = rate;
    utter.pitch = 1;
    utter.onend = () => {
      if (activeRef.current !== item.point_id) return;
      activeRef.current = null;
      setSpeakingId(null);
      void postJson("/api/progress/listen", { point_id: item.point_id }).catch(() => {});
      setItems((list) => list.map((x) => x.point_id === item.point_id
        ? { ...x, heard: true, listen_count: x.listen_count + 1 } : x));
    };
    utter.onerror = () => {
      if (activeRef.current === item.point_id) stop();
    };
    activeRef.current = item.point_id;
    setSpeakingId(item.point_id);
    window.speechSynthesis.speak(utter);
  }

  if (!supported) {
    return (
      <div className="empty">
        当前浏览器不支持语音合成。可以展开每张卡的「查看朗读稿」直接阅读。
      </div>
    );
  }
  if (loading) return <div className="empty">正在取听学队列…</div>;
  if (!items.length) return <div className="empty">这一科没有可朗读的知识点。</div>;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span className="muted" style={{ fontSize: 12 }}>语速</span>
        <div className="rate-select">
          {RATES.map((r) => (
            <button key={r} className={rate === r ? "on" : ""} onClick={() => setRate(r)}>{r}×</button>
          ))}
        </div>
        <button className="ghost" onClick={load}>换一组</button>
      </div>
      <div className="content listen" style={{ padding: 0, margin: 0 }}>
        {items.map((item) => {
          const speaking = speakingId === item.point_id;
          return (
            <article className={`q-card${speaking ? " speaking" : ""}`} key={item.point_id}>
              <div className="card-top">
                <span className="badge kind">{item.kind ?? "朗读"}</span>
                {item.exam_types.map((t) => <span className="badge" key={t}>{t}</span>)}
                {item.heard && <span className="badge">听过 {item.listen_count} 次</span>}
                <span className="spacer" />
                <button className="ai-entry-btn" onClick={() => ai.open({
                  point_id: item.point_id,
                  title: item.title,
                  question: `听不太懂，讲讲「${item.title}」`,
                })}>问 AI</button>
              </div>
              <div className="question">{item.question || item.point}</div>
              <div className="listen-actions">
                <button className="btn primary" onClick={() => speak(item)} disabled={speaking}>
                  {speaking ? "朗读中" : "朗读"}
                </button>
                <button className="btn" onClick={stop} disabled={!speaking}>停止</button>
                <span className="speak-state">{speaking ? "正在朗读…" : item.heard ? "已听过" : "待播放"}</span>
              </div>
              <div className="wave">
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => <i key={i} />)}
              </div>
              <details className="script">
                <summary>查看朗读稿</summary>
                <div dangerouslySetInnerHTML={{ __html: scriptHtml(item.script) }} />
              </details>
              <div className="card-foot">
                <span>{item.chapter_name}</span>
                <span>{esc(item.title)}</span>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}

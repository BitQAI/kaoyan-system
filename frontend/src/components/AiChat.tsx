"use client";
import { useEffect, useRef, useState } from "react";
import { getJson } from "@/lib/api";
import { mdToHtml } from "@/lib/md";
import type { HistoryItem } from "@/lib/types";
import type { AiTarget } from "./AiProvider";

interface Msg { role: "user" | "ai"; text: string }

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* 走下面的兜底 */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return true;
  } catch {
    return false;
  }
}

const SUGGESTIONS = [
  "换个更通俗的说法讲",
  "举个生活里的例子",
  "讲清它和易混概念的区别",
  "这个点在真题里怎么考",
];
const GENERIC = ["今天先复习哪几个点最值？", "某个概念看不懂怎么问？", "怎么安排背诵节奏？"];
const MAX_INPUT_H = 132;

export default function AiChat({
  open, onClose, target,
}: { open: boolean; onClose: () => void; target: AiTarget | null }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [collapsedIds, setCollapsedIds] = useState<Set<number>>(new Set());
  const [tip, setTip] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pointId = target?.point_id ?? "";

  function stopStream() {
    abortRef.current?.abort();
    abortRef.current = null;
  }

  function autosize() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    const h = Math.min(el.scrollHeight, MAX_INPUT_H);
    el.style.height = `${h}px`;
    el.style.overflowY = el.scrollHeight > MAX_INPUT_H ? "auto" : "hidden";
  }

  useEffect(() => { autosize(); }, [input, open]);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => {
      if (window.matchMedia?.("(pointer: fine)").matches) taRef.current?.focus();
    }, 60);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    // 切到新知识点 = 新会话；旧会话留在历史里
    stopStream();
    setMessages([]);
    setInput("");
    setConversationId(null);
    setShowHistory(false);
    setCollapsedIds(new Set());
    setTip("");
    if (target?.question) setInput(target.question);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target?.point_id, target?.question]);

  useEffect(() => {
    if (!open || !pointId) {
      setHistory([]);
      return;
    }
    let cancelled = false;
    getJson<{ items: HistoryItem[] }>(
      `/api/assistant/history?point_id=${encodeURIComponent(pointId)}&limit=20`)
      .then((d) => { if (!cancelled) setHistory(d.items); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [open, pointId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, open]);

  function appendToInput(text: string) {
    if (!text) return;
    setInput((prev) => (prev ? `${prev}\n${text}` : text));
    requestAnimationFrame(() => { autosize(); taRef.current?.focus(); });
  }

  async function handleCopy(text: string) {
    if (!text) return;
    setTip((await copyText(text)) ? "已复制" : "复制失败，请长按手动复制");
  }

  function applyDelta(delta: string) {
    setMessages((m) => {
      const next = [...m];
      const last = next[next.length - 1];
      next[next.length - 1] = { ...last, text: last.text + delta };
      return next;
    });
  }

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setMessages((m) => [...m, { role: "user", text }, { role: "ai", text: "" }]);
    setInput("");
    setBusy(true);
    setTip("");
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch("/api/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          point_id: target?.point_id ?? undefined,
          conversation_id: conversationId ?? undefined,
        }),
        signal: ctrl.signal,
      });
      if (!res.body) throw new Error("无响应流");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const frame of frames) {
          if (!frame.startsWith("data: ")) continue;
          const payload = JSON.parse(frame.slice(6));
          if (payload.type === "delta") applyDelta(payload.delta);
          else if (payload.type === "done") {
            setConversationId(payload.conversation_id);
            refreshHistory();
            window.dispatchEvent(new CustomEvent("ai-asked", {
              detail: { point_id: target?.point_id },
            }));
          } else if (payload.type === "error") {
            applyDelta(`\n\n（${payload.message}）`);
          }
        }
      }
    } catch (e) {
      if (ctrl.signal.aborted) return;
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "ai", text: "连接失败：" + String(e) },
      ]);
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null;
      setBusy(false);
    }
  }

  function refreshHistory() {
    if (!pointId) return;
    getJson<{ items: HistoryItem[] }>(
      `/api/assistant/history?point_id=${encodeURIComponent(pointId)}&limit=20`)
      .then((d) => setHistory(d.items))
      .catch(() => {});
  }

  function toggleCollapsed(id: number) {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (!open) return null;
  const canSend = !busy && input.trim().length > 0;
  const suggestions = pointId ? SUGGESTIONS : GENERIC;

  return (
    <div className="ai-chat" role="dialog" aria-label="AI 助手">
      <div className="ai-chat-head">
        <div className="ai-head-info">
          <span className="ai-dot" />
          <div className="ai-head-text">
            <b>AI 助手</b>
            <span>{target?.title ? `围绕「${target.title}」作答` : "随时提问，讲解会结合知识库"}</span>
          </div>
        </div>
        <button onClick={onClose} aria-label="关闭">×</button>
      </div>

      {(target?.title || target?.description) && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", padding: "8px 12px 0" }}>
          {target?.title && (
            <button className="badge-btn" onClick={() => appendToInput(target.title)}>标题→输入</button>
          )}
          {target?.description && (
            <button className="badge-btn" onClick={() => appendToInput(target.description ?? "")}>描述→输入</button>
          )}
          {tip && <span className="muted" style={{ fontSize: 12 }}>{tip}</span>}
        </div>
      )}

      {pointId && history.length > 0 && (
        <div style={{ padding: "8px 12px 0" }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <button className="badge-btn" onClick={() => setShowHistory((s) => !s)}>
              {showHistory ? "收起历史问答" : `历史问答（${history.length}）`}
            </button>
            {showHistory && (
              collapsedIds.size >= history.length ? (
                <button className="badge-btn" onClick={() => setCollapsedIds(new Set())}>全部展开</button>
              ) : (
                <button className="badge-btn" onClick={() => setCollapsedIds(new Set(history.map((h) => h.id)))}>全部收起</button>
              )
            )}
          </div>
          {showHistory && (
            <div className="ai-history-list">
              {history.map((h) => {
                const collapsed = collapsedIds.has(h.id);
                const preview = h.answer.replace(/\s+/g, " ").slice(0, 120);
                return (
                  <div key={h.id} className="ai-history-item">
                    <p className="muted" style={{ fontSize: 12, margin: 0 }}>{h.ts.slice(0, 16).replace("T", " ")}</p>
                    <div className="chat-msg user" style={{ flexDirection: "column", alignItems: "flex-end" }}>
                      <div className="chat-bubble">{h.question}</div>
                    </div>
                    {collapsed ? (
                      <p className="muted ai-history-preview">答：{preview}{h.answer.length > 120 ? "…" : ""}</p>
                    ) : (
                      <div className="chat-msg ai" style={{ flexDirection: "column", alignItems: "flex-start" }}>
                        <div className="chat-bubble ai-md" style={{ maxWidth: "100%" }}
                          dangerouslySetInnerHTML={{ __html: mdToHtml(h.answer) }} />
                        <button className="badge-btn" style={{ marginTop: 4 }}
                          onClick={() => void handleCopy(h.answer)}>复制回答</button>
                      </div>
                    )}
                    <div className="ai-history-actions">
                      <button className="badge-btn" onClick={() => toggleCollapsed(h.id)}>
                        {collapsed ? "展开全文" : "收起全文"}
                      </button>
                      <button className="badge-btn" onClick={() => {
                        setInput(h.question);
                        setShowHistory(false);
                        requestAnimationFrame(() => { autosize(); taRef.current?.focus(); });
                      }}>回填这个问题</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="ai-chat-body">
        {messages.length === 0 && (
          <div className="ai-empty">
            <div className="ai-empty-icon">✦</div>
            <p>{pointId ? "看不懂就直接问，我会换个说法重讲。" : "随时提问，讲解会结合知识库。"}</p>
            <div className="ai-suggests">
              {suggestions.map((s) => (
                <button key={s} className="ai-suggest" disabled={busy} onClick={() => void ask(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}
            style={{ flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            {m.role === "ai" ? (
              <>
                {m.text ? (
                  <div className={`chat-bubble ai-md${busy && i === messages.length - 1 ? " streaming" : ""}`}
                    style={{ maxWidth: "100%" }}
                    dangerouslySetInnerHTML={{ __html: mdToHtml(m.text) }} />
                ) : (
                  <div className="chat-bubble ai-typing" style={{ maxWidth: "100%" }}>
                    <span /><span /><span />
                  </div>
                )}
                {m.text && (
                  <button className="badge-btn" style={{ marginTop: 4 }}
                    onClick={() => void handleCopy(m.text)}>复制回答</button>
                )}
              </>
            ) : (
              <div className="chat-bubble">{m.text || "…"}</div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="ai-chat-input" onSubmit={(e) => { e.preventDefault(); void ask(input); }}>
        <div className="ai-composer">
          <textarea
            ref={taRef}
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void ask(input);
              }
            }}
            placeholder="输入问题，Enter 发送…"
            disabled={busy}
            aria-label="输入问题"
          />
          <button type="submit" className="ai-send" disabled={!canSend} aria-label="发送">
            {busy ? <span className="ai-spinner" /> : <span>↑</span>}
          </button>
        </div>
        <div className="ai-input-meta">
          <span>Enter 发送 · Shift+Enter 换行</span>
          {input.length > 0 && <span>{input.length} 字</span>}
        </div>
      </form>
    </div>
  );
}

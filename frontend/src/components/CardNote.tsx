"use client";
import { useEffect, useRef, useState } from "react";
import { putJson } from "@/lib/api";

const MAX_LEN = 2000;

/** 每张卡一条笔记，听与记共用；失焦自动保存，也可 ⌘/Ctrl+Enter 手动保存。 */
export default function CardNote({ cardId, note, onSaved }: {
  cardId: string;
  note?: string;
  onSaved: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note ?? "");
  const [saving, setSaving] = useState(false);
  const [tip, setTip] = useState("");
  const savedRef = useRef(note ?? "");
  const tipTimer = useRef<number | null>(null);
  const unmounted = useRef(false);

  useEffect(() => () => {
    unmounted.current = true;
    if (tipTimer.current !== null) window.clearTimeout(tipTimer.current);
  }, []);

  // 换卡时重置；未保存内容靠 textarea 失焦自动保存兜住
  useEffect(() => {
    setEditing(false);
    setDraft(note ?? "");
    savedRef.current = note ?? "";
    setTip("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cardId]);

  function flash(text: string) {
    setTip(text);
    if (tipTimer.current !== null) window.clearTimeout(tipTimer.current);
    tipTimer.current = window.setTimeout(() => {
      if (!unmounted.current) setTip("");
    }, 2000);
  }

  async function save(text: string): Promise<boolean> {
    const content = text.trim();
    if (content === savedRef.current) return true;
    setSaving(true);
    try {
      const d = await putJson<{ content: string }>("/api/notes", {
        card_id: cardId, content,
      });
      savedRef.current = d.content;
      setDraft(d.content);
      onSaved(d.content);
      flash(content ? "已保存" : "已清空笔记");
      return true;
    } catch {
      flash("保存失败，请重试");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function saveAndClose() {
    if (saving) return;
    if (await save(draft)) setEditing(false);
  }

  function cancel() {
    setDraft(savedRef.current);
    setEditing(false);
  }

  function handleBlur(e: React.FocusEvent<HTMLTextAreaElement>) {
    // 点「保存 / 取消」时交给按钮处理，避免自动保存抢在前面把保存态占住
    if ((e.relatedTarget as HTMLElement | null)?.closest(".card-note-actions")) return;
    if (!editing || saving) return;
    if (draft.trim() !== savedRef.current) void save(draft);
  }

  const shown = editing ? draft : savedRef.current;

  return (
    <section className="card-note">
      <div className="card-note-head">
        <h3>我的笔记</h3>
        <span className="card-note-spacer" />
        {tip && <span className="card-note-tip">{tip}</span>}
        {!editing && shown && (
          <button className="badge-btn" onClick={() => setEditing(true)}>编辑</button>
        )}
      </div>

      {editing ? (
        <>
          <textarea
            className="card-note-input"
            value={draft}
            rows={4}
            maxLength={MAX_LEN}
            placeholder="写下你的理解：例句怎么拆、这个词为什么这么用、哪里容易混…"
            onChange={(e) => setDraft(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                void saveAndClose();
              } else if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
            }}
          />
          <div className="card-note-actions">
            <button className="btn primary" disabled={saving}
              onClick={() => void saveAndClose()}>{saving ? "保存中…" : "保存"}</button>
            <button className="btn" disabled={saving} onClick={cancel}>取消</button>
            <span className="card-note-hint">⌘/Ctrl + Enter 保存 · {draft.length}/{MAX_LEN}</span>
          </div>
        </>
      ) : shown ? (
        <div className="card-note-body">{shown}</div>
      ) : (
        <button className="card-note-add" onClick={() => setEditing(true)}>
          ＋ 记下我的理解
        </button>
      )}
    </section>
  );
}

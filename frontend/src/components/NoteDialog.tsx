"use client";
import { useEffect, useRef, useState } from "react";
import { putJson } from "@/lib/api";

const MAX_LEN = 2000;

/** 笔记弹窗：低频功能，入口在顶部工具条，不在卡片正文占位。 */
export default function NoteDialog({ open, cardId, note, onClose, onSaved }: {
  open: boolean;
  cardId: string;
  note?: string;
  onClose: () => void;
  onSaved: (text: string) => void;
}) {
  const [draft, setDraft] = useState(note ?? "");
  const [saving, setSaving] = useState(false);
  const [tip, setTip] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraft(note ?? "");
    setTip("");
    const t = window.setTimeout(() => taRef.current?.focus(), 60);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, cardId]);

  async function save(): Promise<boolean> {
    if (saving) return false;
    setSaving(true);
    try {
      const d = await putJson<{ content: string }>("/api/notes", {
        card_id: cardId, content: draft,
      });
      onSaved(d.content);
      onClose();
      return true;
    } catch {
      setTip("保存失败，请重试");
      return false;
    } finally {
      setSaving(false);
    }
  }

  /** 关闭时若有改动先保存，避免误关丢内容 */
  function close() {
    if (draft.trim() !== (note ?? "").trim()) void save();
    else onClose();
  }

  if (!open) return null;

  return (
    <div className="picker-mask" onClick={close}>
      <div className="picker note-dialog" role="dialog" aria-label="我的笔记"
        onClick={(e) => e.stopPropagation()}>
        <div className="picker-head">
          <b>我的笔记</b>
          <span className="spacer" />
          {tip && <span className="card-note-tip">{tip}</span>}
          <button className="badge-btn" onClick={close}>关闭</button>
        </div>
        <div className="note-dialog-body">
          <textarea
            ref={taRef}
            className="card-note-input"
            value={draft}
            rows={7}
            maxLength={MAX_LEN}
            placeholder="写你的理解：例句怎么拆、作文怎么套、哪里容易混…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                void save();
              }
            }}
          />
          <div className="card-note-actions">
            <button className="btn primary" disabled={saving} onClick={() => void save()}>
              {saving ? "保存中…" : "保存"}
            </button>
            <span className="card-note-hint">
              ⌘/Ctrl + Enter 保存 · 清空后保存即删除 · {draft.length}/{MAX_LEN}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

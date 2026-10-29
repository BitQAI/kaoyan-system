"use client";
import { useEffect, useRef, useState } from "react";
import type { Subject } from "@/lib/types";

const SHORT: Record<string, string> = {
  "812": "植物生理", "315": "化学（农）", "101": "政治", "204": "英语二",
};

export default function SubjectPicker({
  subjects, sid, onPick,
}: { subjects: Subject[]; sid: string; onPick: (sid: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const current = subjects.find((s) => s.id === sid);

  return (
    <div className="subject-picker" ref={ref}>
      <button className="sp-trigger" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox">
        <b>{sid}</b>
        <span>{SHORT[sid] ?? current?.name ?? ""}</span>
        <span className="sp-caret">{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div className="sp-menu" role="listbox">
          {subjects.map((s) => (
            <button
              key={s.id}
              role="option"
              aria-selected={s.id === sid}
              className={`sp-item${s.id === sid ? " on" : ""}`}
              onClick={() => { setOpen(false); onPick(s.id); }}
            >
              <b>{s.id}</b>
              <span>{s.name.replace(/^\d+\s*/, "")}</span>
              <em>{s.chapters.length} 章</em>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

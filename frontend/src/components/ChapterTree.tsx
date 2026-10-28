"use client";
import { useMemo, useState } from "react";
import type { PointIndex, Subject } from "@/lib/types";

export default function ChapterTree({
  subject, points, activePid, onPick,
}: {
  subject: Subject;
  points: PointIndex[];
  activePid: string | null;
  onPick: (pid: string) => void;
}) {
  const byChapter = useMemo(() => {
    const map = new Map<string, PointIndex[]>();
    for (const p of points) {
      const list = map.get(p.chapter_id) ?? [];
      list.push(p);
      map.set(p.chapter_id, list);
    }
    return map;
  }, [points]);

  const [open, setOpen] = useState<Set<string>>(() => new Set());

  function toggle(cid: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(cid)) next.delete(cid);
      else next.add(cid);
      return next;
    });
  }

  let lastModule = "";
  return (
    <aside className="sidebar" aria-label="章节树">
      <div className="sidebar-head">
        <b>{subject.name}</b>
        <span className="spacer" />
        <span className="muted" style={{ fontSize: 12 }}>{subject.chapters.length} 章</span>
      </div>
      {subject.chapters.map((ch) => {
        const showModule = ch.module !== lastModule;
        lastModule = ch.module;
        const items = byChapter.get(ch.id) ?? [];
        const isOpen = open.has(ch.id) || items.some((p) => p.id === activePid);
        return (
          <div key={ch.id}>
            {showModule && <div className="tree-module">{ch.module}</div>}
            <div
              className={`tree-chapter${isOpen && !items.some((p) => p.id === activePid) ? "" : ""}`}
              onClick={() => toggle(ch.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") toggle(ch.id); }}
            >
              <span>{isOpen ? "▾" : "▸"}</span>
              <span>{ch.name}</span>
              <span className="w">{ch.weight_center}分</span>
            </div>
            {isOpen && (
              <>
                {ch.weight_basis === "人工估计" && (
                  <p className="weight-note">权重为人工估计，不保证与满分一致</p>
                )}
                <div className="tree-points">
                  {items.map((p) => (
                    <div
                      key={p.id}
                      className={`tree-point${p.id === activePid ? " on" : ""}`}
                      onClick={() => onPick(p.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === "Enter") onPick(p.id); }}
                    >
                      {p.priority} {p.title}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        );
      })}
    </aside>
  );
}

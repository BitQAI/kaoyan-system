"use client";
import { useEffect, useRef, useState } from "react";
import type { Chapter, PointIndex } from "@/lib/types";

/** 学的知识点导航：一行显示当前位置与前后翻页，点标题展开按章分组的全量目录。 */
export default function PointNav({
  points, chapters, activePid, onPick,
}: {
  points: PointIndex[];
  chapters: Chapter[];
  activePid: string | null;
  onPick: (pid: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const index = points.findIndex((p) => p.id === activePid);
  const current = index >= 0 ? points[index] : null;
  const chapterName = chapters.find((c) => c.id === current?.chapter_id)?.name ?? "";

  function move(delta: number) {
    const next = points[index + delta];
    if (next) onPick(next.id);
  }

  return (
    <>
      <div className="point-nav">
        <button className="pn-arrow" onClick={() => move(-1)} disabled={index <= 0}
          aria-label="上一个知识点">‹</button>
        <button className="pn-current" onClick={() => setOpen(true)} aria-haspopup="dialog">
          <span className="pn-title">
            {current ? `${current.priority} ${current.title}` : "选择知识点"}
          </span>
          <span className="pn-sub">
            {chapterName}
            {points.length > 0 && ` · ${index + 1}/${points.length}`}
            <span className="pn-caret"> ▾</span>
          </span>
        </button>
        <button className="pn-arrow" onClick={() => move(1)}
          disabled={index < 0 || index >= points.length - 1}
          aria-label="下一个知识点">›</button>
      </div>

      {open && (
        <div className="picker-mask" onClick={() => setOpen(false)}>
          <div className="picker pn-sheet" onClick={(e) => e.stopPropagation()} role="dialog"
            aria-label="知识点目录">
            <div className="picker-head">
              <b>知识点目录</b>
              <span className="muted" style={{ fontSize: 12 }}>{points.length} 个</span>
              <span className="spacer" />
              <button className="badge-btn" onClick={() => setOpen(false)}>关闭</button>
            </div>
            <div className="picker-body">
              {chapters.map((ch) => {
                const items = points.filter((p) => p.chapter_id === ch.id);
                if (!items.length) return null;
                return (
                  <div key={ch.id}>
                    <div className="pn-chapter">{ch.name}</div>
                    {items.map((p) => (
                      <button
                        key={p.id}
                        className={`pn-item${p.id === activePid ? " on" : ""}`}
                        onClick={() => { setOpen(false); onPick(p.id); }}
                      >
                        <span className="pn-pri">{p.priority}</span>
                        <span className="pn-item-title">{p.title}</span>
                      </button>
                    ))}
                  </div>
                );
              })}
              {points.length === 0 && <div className="empty">当前范围没有知识点。</div>}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

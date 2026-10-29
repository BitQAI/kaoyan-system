"use client";
import { useEffect, useState } from "react";
import type { Scope } from "@/lib/scope";
import type { Chapter } from "@/lib/types";

export default function RangePicker({
  open, chapters, scope, onClose, onApply,
}: {
  open: boolean;
  chapters: Chapter[];
  scope: Scope;
  onClose: () => void;
  onApply: (scope: Scope) => void;
}) {
  const [picked, setPicked] = useState<Set<string>>(new Set(scope.chapters));
  const [limit, setLimit] = useState(scope.limit);

  useEffect(() => {
    if (open) {
      setPicked(new Set(scope.chapters));
      setLimit(scope.limit);
    }
  }, [open, scope]);

  if (!open) return null;

  function toggle(id: string) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  let lastModule = "";
  return (
    <div className="picker-mask" onClick={onClose}>
      <div className="picker" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="自定义范围">
        <div className="picker-head">
          <b>自定义范围</b>
          <span className="muted" style={{ fontSize: 12 }}>不选 = 该科全部章节</span>
          <span className="spacer" />
          <button className="badge-btn" onClick={onClose}>关闭</button>
        </div>

        <div className="picker-body">
          {chapters.map((ch) => {
            const showModule = ch.module !== lastModule;
            lastModule = ch.module;
            return (
              <div key={ch.id}>
                {showModule && <div className="tree-module">{ch.module}</div>}
                <label className="picker-row">
                  <input type="checkbox" checked={picked.has(ch.id)} onChange={() => toggle(ch.id)} />
                  <span>{ch.name}</span>
                  <span className="spacer" />
                  <span className="muted" style={{ fontSize: 11.5 }}>{ch.weight_center} 分 · {ch.entry_count} 点</span>
                </label>
              </div>
            );
          })}
        </div>

        <div className="picker-foot">
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            每批
            <input
              type="number" min={5} max={100} value={limit}
              onChange={(e) => setLimit(Math.max(1, Math.min(100, Number(e.target.value) || 20)))}
              style={{ width: 72, padding: "6px 8px", borderRadius: 9, border: "1px solid var(--line)", background: "var(--bg2)", color: "var(--ink)" }}
            />
            条
          </label>
          <span className="spacer" />
          <button className="badge-btn" onClick={() => setPicked(new Set())}>清空选择</button>
          <button className="btn primary" onClick={() => onApply({ chapters: [...picked], limit })}>
            应用{picked.size ? `（${picked.size} 章）` : "（全部）"}
          </button>
        </div>
      </div>
    </div>
  );
}

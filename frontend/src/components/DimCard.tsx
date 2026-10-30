"use client";
import type { DimStat } from "@/lib/progress-types";
import { STATUS_LABEL, finishLabel } from "@/lib/progress-labels";

export default function DimCard({ kind, dim }: { kind: "memo" | "listen"; dim: DimStat }) {
  return (
    <div className={`dim-card tone-${kind}`}>
      <div className="dim-title">
        <i className={`dim-dot ${kind}`} />
        {dim.label}
      </div>
      <div className="dim-pct">
        {dim.percent.toFixed(1)}<span>%</span>
      </div>
      <div className="dim-sub">{dim.done}/{dim.total} {dim.unit}</div>
      <div className="dim-foot">
        <span className={`dh-pill st-${dim.status}`}>{STATUS_LABEL[dim.status] ?? dim.status}</span>
        <span className="muted">{finishLabel(dim)}</span>
      </div>
      <p className={`dim-note st-${dim.status}`}>{dim.status_text}</p>
      {dim.capacity && (
        <p className="dim-load muted">
          复习占用 {dim.capacity.review_load} 张/天 · 可分配新卡 {dim.capacity.new_pace} 张/天
        </p>
      )}
      {dim.confidence === "low" && (
        <p className="dim-load muted">数据不足，仅供参考</p>
      )}
    </div>
  );
}

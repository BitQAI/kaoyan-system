"use client";
import type { DimStat } from "@/lib/progress-types";
import { STATUS_LABEL, finishLabel } from "@/lib/progress-labels";

function DimRow({ kind, dim }: { kind: "memo" | "listen"; dim: DimStat }) {
  const note = dim.status !== "ok" && dim.status !== "empty";
  return (
    <div className={`dim-row tone-${kind}`}>
      <div className="dim-row-head">
        <span className="dim-title"><i className={`dim-dot ${kind}`} />{dim.label}</span>
        <span className="dim-pct-inline">{dim.percent.toFixed(1)}<em>%</em></span>
        <span className="dim-count">{dim.done}/{dim.total} {dim.unit}</span>
        <span className={`dh-pill st-${dim.status}`}>
          {STATUS_LABEL[dim.status] ?? dim.status}
        </span>
      </div>
      <div className="dim-bar">
        <i className={kind} style={{ width: `${Math.min(100, dim.percent)}%` }} />
      </div>
      <div className="dim-meta">
        <span>{finishLabel(dim)}</span>
        {dim.capacity && (
          <span>复习 {dim.capacity.review_load} · 可分配 {dim.capacity.new_pace} 张/天</span>
        )}
        {dim.confidence === "low" && dim.status !== "insufficient" && (
          <span className="dim-warn">数据不足，仅供参考</span>
        )}
      </div>
      {note && <p className={`dim-note st-${dim.status}`}>{dim.status_text}</p>}
    </div>
  );
}

export default function DimSummary({ memo, listen }: { memo: DimStat; listen: DimStat }) {
  return (
    <div className="dim-summary">
      <DimRow kind="memo" dim={memo} />
      <DimRow kind="listen" dim={listen} />
    </div>
  );
}

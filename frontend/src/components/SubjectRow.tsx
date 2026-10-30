"use client";
import type { SubjectLine, SubjectDim } from "@/lib/progress-types";
import { STATUS_LABEL } from "@/lib/progress-labels";

function eta(dim: SubjectDim): string {
  return dim.finish_date ? `预计 ${dim.finish_date}` : "暂无预测";
}

export default function SubjectRow({ s }: { s: SubjectLine }) {
  const rows: ["memo" | "listen", SubjectDim][] = [
    ["memo", s.memo],
    ["listen", s.listen],
  ];
  return (
    <div className="sl-row">
      <div className="sl-head">
        <b>{s.name}</b>
        <span className="sl-chips">
          {rows.map(([kind, d]) => (
            <span key={kind} className={`sl-chip st-${d.status}`}>
              {kind === "memo" ? "记" : "听"} {STATUS_LABEL[d.status] ?? d.status}
            </span>
          ))}
        </span>
      </div>
      {rows.map(([kind, d]) => (
        <div className="sl-metric" key={kind}>
          <span className={`sl-tag ${kind}`}>{kind === "memo" ? "记" : "听"}</span>
          <span className="sl-bar">
            <i className={kind} style={{ width: `${Math.min(100, d.percent)}%` }} />
          </span>
          <span className="sl-num">{d.percent.toFixed(1)}%</span>
          <span className="muted sl-count">{d.done}/{d.total}</span>
        </div>
      ))}
      <div className="sl-eta muted">
        <span>记 {eta(s.memo)}</span>
        <span>听 {eta(s.listen)}</span>
      </div>
    </div>
  );
}

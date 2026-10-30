"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import ProgressChart from "./ProgressChart";
import DimSummary from "./DimSummary";
import SubjectRow from "./SubjectRow";
import { demoData } from "@/lib/progress-demo";
import type { ChartLine, Timeline } from "@/lib/progress-types";
import { TREND_LABEL } from "@/lib/progress-labels";

export default function ProgressDashboard() {
  const [data, setData] = useState<Timeline | null>(null);
  const [scope, setScope] = useState<string>("all");
  const [demo, setDemo] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (demo) return;
    setError("");
    getJson<Timeline>(`/api/stats/timeline?days=21${scope === "all" ? "" : `&sid=${scope}`}`)
      .then(setData).catch((e) => setError(String(e)));
  }, [scope, demo]);

  const view = demo ? demoData() : data;
  const subjects = data?.subjects ?? [];
  const memo = view?.dimensions.memo;
  const listen = view?.dimensions.listen;
  const lines: ChartLine[] = memo && listen ? [
    { key: "memo", label: memo.label, tone: "memo", series: memo.series },
    { key: "listen", label: listen.label, tone: "listen", series: listen.series },
  ] : [];
  const summary = memo && listen
    ? `记完成 ${memo.percent.toFixed(1)}%，${memo.status_text}；`
      + `听完成 ${listen.percent.toFixed(1)}%，${listen.status_text}`
    : undefined;
  const stalled = view
    ? (["memo", "listen"] as const).filter((k) => view.dimensions[k].status === "stalled")
    : [];

  return (
    <section className="dashboard">
      {demo && (
        <div className="demo-banner">
          这是示例数据，用于预览图表效果，不是你的真实学习记录
          <button className="badge-btn" onClick={() => setDemo(false)}>回到真实数据</button>
        </div>
      )}

      {!view && !error && <div className="empty">加载中…</div>}
      {error && <div className="empty">加载失败：{error}</div>}

      {view && memo && listen && (
        <>
          <DimSummary memo={memo} listen={listen} />

          <div className="habit-line">
            <span>距初试 <b>{view.days_left}</b> 天</span>
            <span>连续 <b>{view.streak ?? 0}</b> 天</span>
            <span>今日 记 <b>{view.daily?.cards ?? 0}</b> · 听 <b>{view.daily?.listened ?? 0}</b></span>
            <span>今日到期 <b>{view.review_load?.due_today ?? 0}</b> 张</span>
          </div>

          <div className="chart-card">
            <ProgressChart lines={lines} examDate={view.exam_date}
              today={view.today} summary={summary} />
            <div className="chart-legend">
              <span><i className="lg-solid memo" />记</span>
              <span><i className="lg-solid listen" />听</span>
              <span><i className="lg-dash" />预测</span>
              <span><i className="lg-band" />80% 预测区间</span>
              <span><i className="lg-ideal" />所需速度</span>
              <span><i className="lg-goal" />初试</span>
            </div>
            <div className="chart-foot">
              <span>
                近期日均：记 {memo.pace}（{TREND_LABEL[memo.pace_trend ?? "flat"]}）
                · 听 {listen.pace}（{TREND_LABEL[listen.pace_trend ?? "flat"]}）
              </span>
              <span>
                赶上初试需：记 {memo.required_pace ?? "—"} · 听 {listen.required_pace ?? "—"} 张/天
              </span>
            </div>
          </div>

          {stalled.map((k) => (
            <p className="chart-stall" key={k}>
              {view.dimensions[k].label}近 7 天没有新增，先恢复学习节奏。
            </p>
          ))}

          <div className="scope-tabs">
            <button className={scope === "all" && !demo ? "on" : ""}
              onClick={() => { setDemo(false); setScope("all"); }}>整体</button>
            {subjects.map((s) => (
              <button key={s.id} className={scope === s.id && !demo ? "on" : ""}
                onClick={() => { setDemo(false); setScope(s.id); }}>
                {s.id}
              </button>
            ))}
            <button className={demo ? "on demo" : "demo"} onClick={() => setDemo((d) => !d)}
              title="用示例数据预览图表效果">
              {demo ? "退出示例" : "示例"}
            </button>
          </div>

          {!demo && (
            <>
              <div className="subject-list">
                {subjects.map((s) => <SubjectRow key={s.id} s={s} />)}
              </div>

              <details className="more-block">
                <summary>更多数据</summary>
                <div className="weekly-row">
                  <span>本周记了 <b>{view.weekly?.this_week ?? 0}</b> 张</span>
                  {view.weekly?.delta_pct === null || view.weekly?.delta_pct === undefined ? (
                    <span className="muted">上周没有记录，下周就能比了</span>
                  ) : (
                    <span className={view.weekly.delta_pct >= 0 ? "wk-up" : "wk-down"}>
                      较上周 {view.weekly.delta_pct >= 0 ? "+" : ""}{view.weekly.delta_pct}%
                    </span>
                  )}
                </div>

                {view.milestones && (
                  <div className="ms-block">
                    {view.milestones.items.length > 0 && (
                      <div className="ms-list">
                        {view.milestones.items.map((m) => (
                          <span className="ms-chip" key={m.key}>✓ {m.label}</span>
                        ))}
                      </div>
                    )}
                    {view.milestones.next && (
                      <div className="ms-next">
                        <span className="muted">下一个：{view.milestones.next.label}</span>
                        <span className="ms-bar">
                          <i style={{ width: `${view.milestones.next.pct}%` }} />
                        </span>
                        <span className="muted">
                          {view.milestones.next.current}/{view.milestones.next.target}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {(["memo", "listen"] as const).map((k) => {
                  const dim = view.dimensions[k];
                  if (!dim.data_quality.derived_cards) return null;
                  return (
                    <p className="muted dq-note" key={k}>
                      {dim.label}：{dim.data_quality.derived_cards} 张是按最近一次记录推算的
                      （早期没有逐次流水），之后每天的记录都是精确的。
                    </p>
                  );
                })}
              </details>
            </>
          )}
        </>
      )}
    </section>
  );
}

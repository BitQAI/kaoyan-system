"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import ProgressChart, { type SeriesPoint } from "./ProgressChart";

interface SubjectLine {
  id: string; name: string; total: number; done: number; percent: number;
  pace: number; finish_date: string | null; status: string;
}
export interface Timeline {
  today: string; exam_date: string; days_left: number;
  scope: string; total: number; done: number; percent: number;
  status: "ok" | "risk" | "late" | "empty" | "insufficient";
  status_text: string;
  pace: number; pace_window: number; required_pace: number | null;
  finish_date: string | null;
  series: SeriesPoint[];
  subjects: SubjectLine[];
  data_quality: { derived_cards: number; recorded_cards: number };
}

const STATUS_LABEL: Record<string, string> = {
  ok: "按计划", risk: "有风险", late: "来不及", insufficient: "数据不足", empty: "无记录",
};

/** 示例数据：只在用户主动点「看示例」时使用，界面上明确标注，不会混进真实统计。 */
function demoData(): Timeline {
  const today = new Date();
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const series: SeriesPoint[] = [];
  const exam = new Date(today.getTime() + 51 * 86400000);
  let acc = 0;
  for (let i = 20; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400000);
    acc += i === 20 ? 0 : Math.round(8 + Math.random() * 6);
    series.push({ date: iso(d), done: acc, percent: +(acc / 900 * 100).toFixed(2), actual: true });
  }
  const pace = 11;
  for (let i = 1; today.getTime() + i * 86400000 <= exam.getTime(); i++) {
    const d = new Date(today.getTime() + i * 86400000);
    const n = acc + pace * i;
    series.push({ date: iso(d), done: n, percent: +(Math.min(n, 900) / 900 * 100).toFixed(2), actual: false });
  }
  return {
    today: iso(today), exam_date: iso(exam), days_left: 51, scope: "all",
    total: 900, done: acc, percent: +(acc / 900 * 100).toFixed(2),
    status: "ok", status_text: "按当前速度可以在初试前学完",
    pace, pace_window: 7, required_pace: 6.2,
    finish_date: iso(new Date(today.getTime() + Math.round((900 - acc) / pace) * 86400000)),
    series,
    subjects: [
      { id: "812", name: "812 植物生理学", total: 260, done: 150, percent: 57.7, pace: 4.2, finish_date: iso(exam), status: "ok" },
      { id: "315", name: "315 化学（农）", total: 360, done: 120, percent: 33.3, pace: 3.1, finish_date: iso(exam), status: "risk" },
      { id: "101", name: "101 思想政治理论", total: 200, done: 40, percent: 20, pace: 1.6, finish_date: iso(exam), status: "risk" },
      { id: "204", name: "204 英语（二）", total: 80, done: 60, percent: 75, pace: 2.1, finish_date: iso(exam), status: "ok" },
    ],
    data_quality: { derived_cards: 0, recorded_cards: 150 },
  };
}

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

      {view && (
        <>
          <div className="dh">
            <div className="dh-left">
              <div className="dh-pct">{view.percent.toFixed(1)}%</div>
              <div className="dh-sub">
                {view.done}/{view.total} 张 · 距初试 {view.days_left} 天
                {view.finish_date && view.status !== "insufficient"
                  ? ` · 预计 ${view.finish_date} 学完` : ""}
              </div>
            </div>
            <span className={`dh-pill st-${view.status}`}>{STATUS_LABEL[view.status] ?? view.status}</span>
          </div>
          <p className={`dh-note st-${view.status}`}>{view.status_text}</p>

          <div className="chart-card">
            <ProgressChart series={view.series} examDate={view.exam_date} today={view.today} />
            <div className="chart-legend">
              <span><i className="lg-ac" />实际</span>
              <span><i className="lg-fc" />预测</span>
              <span><i className="lg-goal" />100% / 初试</span>
            </div>
            <div className="chart-foot">
              <span>近 {view.pace_window} 天日均 {view.pace} 张</span>
              {view.required_pace !== null && view.required_pace > 0 && (
                <span>要在初试前学完，需 {view.required_pace} 张/天</span>
              )}
            </div>
          </div>

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
            <div className="subject-list">
              {subjects.map((s) => (
                <div className="sl-row" key={s.id}>
                  <div className="sl-head">
                    <b>{s.name}</b>
                    <span className="muted">{s.done}/{s.total}</span>
                  </div>
                  <div className="sl-bar"><i style={{ width: `${Math.min(100, s.percent)}%` }} /></div>
                  <div className="sl-foot">
                    <span className="muted">日均 {s.pace} 张</span>
                    <span className={`st-${s.status}`}>
                      {s.status === "empty" ? "无记录"
                        : s.finish_date ? `${s.finish_date} 学完` : "数据不足"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!demo && view.data_quality.derived_cards > 0 && (
            <p className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
              其中 {view.data_quality.derived_cards} 张是按卡片最后复习时间推算的（早于事件记录的引入），
              之后每天的记录都是精确的。
            </p>
          )}


        </>
      )}
    </section>
  );
}

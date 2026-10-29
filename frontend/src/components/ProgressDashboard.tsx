"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import ProgressChart, { type ChartLine, type SeriesPoint } from "./ProgressChart";

type DimStatus = "ok" | "risk" | "late" | "empty" | "insufficient";

export interface DimStat {
  label: string; unit: string;
  total: number; done: number; percent: number;
  status: DimStatus; status_text: string;
  pace: number; pace_window: number; required_pace: number | null;
  finish_date: string | null;
  series: SeriesPoint[];
  data_quality: { derived_cards: number; recorded_cards: number };
}

interface SubjectDim {
  total: number; done: number; percent: number;
  pace: number; finish_date: string | null; status: DimStatus;
}

interface SubjectLine {
  id: string; name: string;
  memo: SubjectDim; listen: SubjectDim;
}

export interface Timeline {
  today: string; exam_date: string; days_left: number; scope: string;
  dimensions: { memo: DimStat; listen: DimStat };
  subjects: SubjectLine[];
  streak: number;
  daily: { goal: number; cards: number; listened: number; read: number };
  weekly: { this_week: number; last_week: number; delta_pct: number | null; week_start: string };
  milestones: {
    count: number;
    items: { key: string; label: string }[];
    next: { label: string; current: number; target: number; kind: string; pct: number } | null;
  };
}

const STATUS_LABEL: Record<string, string> = {
  ok: "按计划", risk: "有风险", late: "来不及", insufficient: "数据不足", empty: "无记录",
};

const iso = (d: Date) => d.toISOString().slice(0, 10);
const pct = (done: number, total: number) => (total ? +((done / total) * 100).toFixed(2) : 0);

/** 示例数据：只在用户主动点「示例」时使用，界面上明确标注，不会混进真实统计。 */
function demoDim(label: string, total: number, pace: number, today: Date, exam: Date): DimStat {
  const series: SeriesPoint[] = [];
  let acc = 0;
  const hist = 20;
  for (let i = hist; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 864e5);
    if (i < hist) acc += pace;
    series.push({ date: iso(d), done: acc, percent: pct(acc, total), actual: true });
  }
  const finish = new Date(today.getTime() + Math.ceil((total - acc) / pace) * 864e5);
  const end = Math.min(finish.getTime(), exam.getTime());
  for (let t = today.getTime() + 864e5; t <= end; t += 864e5) {
    const n = Math.min(total, acc + Math.round(pace * ((t - today.getTime()) / 864e5)));
    series.push({ date: iso(new Date(t)), done: n, percent: pct(n, total), actual: false });
  }
  const left = Math.max(1, Math.round((exam.getTime() - today.getTime()) / 864e5));
  return {
    label, unit: "张", total, done: acc, percent: pct(acc, total),
    status: "ok", status_text: "按当前速度可以在初试前学完",
    pace, pace_window: 7, required_pace: +((total - acc) / left).toFixed(2),
    finish_date: iso(finish), series,
    data_quality: { derived_cards: 0, recorded_cards: acc },
  };
}

function demoSubject(id: string, name: string, total: number, memoRate: number,
                     listenRate: number, exam: string): SubjectLine {
  const dim = (rate: number, pace: number): SubjectDim => {
    const done = Math.round(total * rate);
    return { total, done, percent: pct(done, total), pace, finish_date: exam, status: "ok" };
  };
  return { id, name, memo: dim(memoRate, 2.4), listen: dim(listenRate, 1.7) };
}

function demoData(): Timeline {
  const today = new Date();
  const exam = new Date(today.getTime() + 51 * 864e5);
  const examIso = iso(exam);
  return {
    today: iso(today), exam_date: examIso, days_left: 51, scope: "all",
    dimensions: {
      memo: demoDim("记", 3171, 12, today, exam),
      listen: demoDim("听", 3171, 8, today, exam),
    },
    subjects: [
      demoSubject("812", "812 植物生理学", 780, 0.57, 0.44, examIso),
      demoSubject("315", "315 化学（农）", 1120, 0.33, 0.26, examIso),
      demoSubject("101", "101 思想政治理论", 870, 0.2, 0.18, examIso),
      demoSubject("204", "204 英语（二）", 401, 0.75, 0.61, examIso),
    ],
    streak: 6,
    daily: { goal: 30, cards: 18, listened: 12, read: 5 },
    weekly: { this_week: 86, last_week: 62, delta_pct: 39, week_start: iso(today) },
    milestones: {
      count: 3,
      items: [
        { key: "streak-3", label: "连续学习 3 天" },
        { key: "streak-7", label: "连续学习 7 天" },
        { key: "chapter-812-02", label: "第二章 植物的水分代谢 全部读完" },
      ],
      next: { label: "累计记满 500 张", current: 240, target: 500, kind: "cards", pct: 48 },
    },
  };
}

function DimCard({ kind, dim }: { kind: string; dim: DimStat }) {
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
        <span className="muted">
          {dim.finish_date && dim.status !== "insufficient" && dim.status !== "empty"
            ? `预计 ${dim.finish_date}` : "暂无预测"}
        </span>
      </div>
      <p className={`dim-note st-${dim.status}`}>{dim.status_text}</p>
    </div>
  );
}

function SubjectRow({ s }: { s: SubjectLine }) {
  const rows: [string, SubjectDim][] = [["memo", s.memo], ["listen", s.listen]];
  return (
    <div className="sl-row">
      <div className="sl-head"><b>{s.name}</b></div>
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
    </div>
  );
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
  const memo = view?.dimensions.memo;
  const listen = view?.dimensions.listen;
  const lines: ChartLine[] = memo && listen ? [
    { key: "memo", label: memo.label, tone: "memo", series: memo.series },
    { key: "listen", label: listen.label, tone: "listen", series: listen.series },
  ] : [];

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
          <div className="dim-head">
            <DimCard kind="memo" dim={memo} />
            <DimCard kind="listen" dim={listen} />
          </div>

          <div className="habit-line">
            <span>距初试 <b>{view.days_left}</b> 天</span>
            <span>连续 <b>{view.streak ?? 0}</b> 天</span>
            <span>今日 记 <b>{view.daily?.cards ?? 0}</b> · 听 <b>{view.daily?.listened ?? 0}</b></span>
          </div>

          <div className="chart-card">
            <ProgressChart lines={lines} examDate={view.exam_date} today={view.today} />
            <div className="chart-legend">
              <span><i className="lg-solid memo" />记</span>
              <span><i className="lg-solid listen" />听</span>
              <span><i className="lg-dash" />预测</span>
              <span><i className="lg-goal" />初试</span>
            </div>
            <div className="chart-foot">
              <span>近 {memo.pace_window} 天日均：记 {memo.pace} · 听 {listen.pace} 张</span>
              <span>
                赶上初试需：记 {memo.required_pace ?? "—"} · 听 {listen.required_pace ?? "—"} 张/天
              </span>
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

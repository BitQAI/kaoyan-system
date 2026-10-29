"use client";
import { useMemo } from "react";

export interface SeriesPoint {
  date: string;
  done: number;
  percent: number;
  actual: boolean;
}

export interface ChartLine {
  key: string;
  label: string;
  tone: "memo" | "listen";
  series: SeriesPoint[];
}

const W = 720;
const H = 240;
const PAD = { l: 46, r: 18, t: 18, b: 30 };
const DAY = 86400000;

const TONE_COLOR: Record<ChartLine["tone"], string> = {
  memo: "var(--chart-ac)",
  listen: "var(--accent)",
};

function md(iso: string): string {
  return iso.slice(5).replace("-", "/");
}

function dayNum(iso: string): number {
  return Date.parse(`${iso}T00:00:00Z`) / DAY;
}

/** 进度曲线：记 / 听 两条实际线 + 同色虚线预测，横轴按真实日期铺开。 */
export default function ProgressChart({
  lines, examDate, today, height = H,
}: {
  lines: ChartLine[];
  examDate: string;
  today: string;
  height?: number;
}) {
  const geo = useMemo(() => {
    const pts = lines.flatMap((l) => l.series);
    if (!pts.length) return null;

    const days = pts.map((p) => dayNum(p.date));
    const dMin = Math.min(...days);
    const dMax = Math.max(...days);
    const innerW = W - PAD.l - PAD.r;
    const innerH = height - PAD.t - PAD.b;
    const x = (iso: string) => PAD.l + (dMax === dMin ? innerW
      : ((dayNum(iso) - dMin) / (dMax - dMin)) * innerW);
    const maxPct = Math.max(100, ...pts.map((p) => p.percent));
    const yMax = maxPct <= 100 ? 100 : Math.ceil(maxPct / 20) * 20;
    const y = (pct: number) => PAD.t + innerH - (pct / yMax) * innerH;

    const seq = (list: SeriesPoint[]) => list
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.date).toFixed(1)},${y(p.percent).toFixed(1)}`)
      .join(" ");

    const paths = lines.map((line) => {
      const actual = line.series.filter((p) => p.actual);
      const tail = line.series.filter((p) => !p.actual);
      const forecast = [...actual.slice(-1), ...tail];
      return {
        key: line.key,
        color: TONE_COLOR[line.tone],
        actual: actual.length > 1 ? seq(actual) : "",
        forecast: tail.length ? seq(forecast) : "",
        todayPct: line.series.find((p) => p.date === today)?.percent,
      };
    });

    const dates = [...new Set(pts.map((p) => p.date))].sort();
    const first = dates[0];
    const last = dates[dates.length - 1];
    const marks: { date: string; anchor: "start" | "middle" | "end" }[] = [];
    // 太近的日期标签会糊在一起，按 first → today → 初试 → last 的优先级丢弃
    const addMark = (date: string, anchor: "start" | "middle" | "end") => {
      if (date < first || date > last) return;
      if (marks.some((m) => Math.abs(x(m.date) - x(date)) < 46)) return;
      marks.push({ date, anchor });
    };
    addMark(first, "start");
    if (today !== first) addMark(today, "middle");
    if (examDate !== today) addMark(examDate, "middle");
    addMark(last, "end");

    return { paths, yMax, y, x, marks, first, last };
  }, [lines, examDate, today, height]);

  if (!geo) return null;
  const { paths, yMax, y, x, marks, first, last } = geo;
  const ticks = yMax <= 100 ? [0, 50, 100] : [0, Math.round(yMax / 2), yMax];

  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="progress-chart" role="img"
      aria-label="记与听的学习进度曲线与预测">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)}
            stroke="var(--line)" strokeWidth="1" />
          <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" className="pc-axis">{t}%</text>
        </g>
      ))}

      <line x1={PAD.l} x2={W - PAD.r} y1={y(100)} y2={y(100)}
        stroke="var(--chart-goal)" strokeWidth="1" strokeDasharray="5 5" opacity=".7" />

      {examDate >= first && examDate <= last && (
        <line x1={x(examDate)} x2={x(examDate)} y1={PAD.t} y2={height - PAD.b}
          stroke="var(--chart-goal)" strokeWidth="1" strokeDasharray="3 4" opacity=".7" />
      )}

      {paths.map((p) => p.forecast && (
        <path key={`f-${p.key}`} d={p.forecast} fill="none" stroke={p.color}
          strokeWidth="2.2" strokeLinecap="round" strokeDasharray="6 4" opacity=".85" />
      ))}
      {paths.map((p) => p.actual && (
        <path key={`a-${p.key}`} d={p.actual} fill="none" stroke={p.color}
          strokeWidth="2.8" strokeLinecap="round" />
      ))}
      {paths.map((p) => p.todayPct !== undefined && (
        <circle key={`t-${p.key}`} cx={x(today)} cy={y(p.todayPct)} r="4.5"
          fill={p.color} stroke="var(--card-strong)" strokeWidth="2" />
      ))}

      {marks.map((m) => (
        <text key={m.date} x={x(m.date)} y={height - 8} textAnchor={m.anchor}
          className="pc-axis">{md(m.date)}</text>
      ))}
    </svg>
  );
}

"use client";
import { useMemo } from "react";

export interface SeriesPoint {
  date: string;
  done: number;
  percent: number;
  actual: boolean;
}

const W = 720;
const H = 240;
const PAD = { l: 46, r: 18, t: 18, b: 30 };

function md(iso: string): string {
  return iso.slice(5).replace("-", "/");
}

/** 进度曲线：绿色实际线 + 琥珀色预测线 + 斜纹预测区 + 100% 基准虚线。 */
export default function ProgressChart({
  series, examDate, today, height = H,
}: {
  series: SeriesPoint[];
  examDate: string;
  today: string;
  height?: number;
}) {
  const geo = useMemo(() => {
    const pts = series.length ? series : [];
    const maxPct = Math.max(100, ...pts.map((p) => p.percent));
    const yMax = maxPct <= 100 ? 100 : Math.ceil(maxPct / 20) * 20;
    const innerW = W - PAD.l - PAD.r;
    const innerH = height - PAD.t - PAD.b;
    const x = (i: number) => PAD.l + (pts.length <= 1 ? innerW : (i / (pts.length - 1)) * innerW);
    const y = (pct: number) => PAD.t + innerH - (pct / yMax) * innerH;

    const actual = pts.filter((p) => p.actual);
    const forecastTail = pts.filter((p) => !p.actual);
    const forecast = [...(actual.slice(-1)), ...forecastTail];

    const line = (list: SeriesPoint[]) => list
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(pts.indexOf(p)).toFixed(1)},${y(p.percent).toFixed(1)}`)
      .join(" ");

    const area = forecast.length
      ? `${line(forecast)} L${x(pts.indexOf(forecast[forecast.length - 1])).toFixed(1)},${y(0).toFixed(1)} ` +
        `L${x(pts.indexOf(forecast[0])).toFixed(1)},${y(0).toFixed(1)} Z`
      : "";

    const todayIdx = pts.findIndex((p) => p.date === today);
    const examIdx = pts.findIndex((p) => p.date === examDate);
    const finishIdx = pts.findIndex((p) => !p.actual && p.percent >= 100);
    return { pts, yMax, x, y, actualPath: line(actual), forecastPath: line(forecast),
      areaPath: area, todayIdx, examIdx, finishIdx, innerH };
  }, [series, examDate, today, height]);

  if (!geo.pts.length) return null;
  const { pts, yMax, x, y, actualPath, forecastPath, areaPath, todayIdx, examIdx, finishIdx } = geo;

  const ticks = yMax <= 100 ? [0, 50, 100] : [0, Math.round(yMax / 2), yMax];
  const labelIdx = new Set<number>([0, pts.length - 1]);
  if (todayIdx > 0 && todayIdx < pts.length - 1) labelIdx.add(todayIdx);
  if (examIdx > 0 && examIdx < pts.length - 1) labelIdx.add(examIdx);

  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="progress-chart" role="img"
      aria-label="学习进度曲线与预测">
      <defs>
        <pattern id="hatch" width="7" height="7" patternTransform="rotate(45)"
          patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="7" stroke="var(--chart-fc)" strokeWidth="2" opacity=".28" />
        </pattern>
      </defs>

      {ticks.map((t) => (
        <g key={t}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)}
            stroke="var(--line)" strokeWidth="1" />
          <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" className="pc-axis">{t}%</text>
        </g>
      ))}

      <line x1={PAD.l} x2={W - PAD.r} y1={y(100)} y2={y(100)}
        stroke="var(--chart-goal)" strokeWidth="1" strokeDasharray="5 5" opacity=".7" />

      {areaPath && <path d={areaPath} fill="url(#hatch)" />}
      {forecastPath && (
        <path d={forecastPath} fill="none" stroke="var(--chart-fc)" strokeWidth="2.4"
          strokeLinecap="round" strokeDasharray="6 4" />
      )}
      {actualPath && (
        <path d={actualPath} fill="none" stroke="var(--chart-ac)" strokeWidth="2.8"
          strokeLinecap="round" />
      )}

      {examIdx >= 0 && (
        <line x1={x(examIdx)} x2={x(examIdx)} y1={PAD.t} y2={height - PAD.b}
          stroke="var(--chart-goal)" strokeWidth="1" strokeDasharray="3 4" opacity=".7" />
      )}

      {todayIdx >= 0 && (
        <circle cx={x(todayIdx)} cy={y(pts[todayIdx].percent)} r="4.5"
          fill="var(--chart-ac)" stroke="var(--card-strong)" strokeWidth="2" />
      )}
      {finishIdx >= 0 && (
        <>
          <circle cx={x(finishIdx)} cy={y(100)} r="4" fill="var(--chart-fc)"
            stroke="var(--card-strong)" strokeWidth="2" />
          <text x={x(finishIdx)} y={y(100) - 10} textAnchor="middle" className="pc-flag">
            {md(pts[finishIdx].date)}
          </text>
        </>
      )}

      {[...labelIdx].sort((a, b) => a - b).map((i) => (
        <text key={i} x={x(i)} y={height - 8}
          textAnchor={i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle"}
          className="pc-axis">{md(pts[i].date)}</text>
      ))}
    </svg>
  );
}

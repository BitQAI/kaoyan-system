"use client";
import { useMemo, useState } from "react";
import type { ChartLine, SeriesPoint } from "@/lib/progress-types";

const W = 720;
const H = 240;
const PAD = { l: 46, r: 18, t: 18, b: 30 };
const DAY = 86400000;

const TONE_COLOR: Record<ChartLine["tone"], string> = {
  memo: "var(--chart-ac)",
  listen: "var(--accent)",
};
const DASH: Record<ChartLine["tone"], string> = { memo: "6 4", listen: "2 3" };

const md = (iso: string): string => iso.slice(5).replace("-", "/");
const dayNum = (iso: string): number => Date.parse(`${iso}T00:00:00Z`) / DAY;

function pointAt(series: SeriesPoint[], date: string): SeriesPoint | undefined {
  let found: SeriesPoint | undefined;
  for (const p of series) {
    if (p.date === date) return p;
    if (p.date < date) found = p;
    else break;
  }
  return found;
}

export default function ProgressChart({
  lines, examDate, today, height = H, summary,
}: {
  lines: ChartLine[];
  examDate: string;
  today: string;
  height?: number;
  summary?: string;
}) {
  const [active, setActive] = useState<string | null>(null);

  const geo = useMemo(() => {
    const pts = lines.flatMap((l) => l.series);
    if (!pts.length) return null;

    const days = pts.map((p) => dayNum(p.date));
    const dMin = Math.min(...days);
    const dMax = Math.max(...days, dayNum(examDate));
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
      const bandPts = tail.filter((p) => p.low_pct !== undefined && p.high_pct !== undefined);
      const band = bandPts.length > 1
        ? bandPts.map((p, i) =>
            `${i === 0 ? "M" : "L"}${x(p.date).toFixed(1)},${y(p.high_pct!).toFixed(1)}`).join(" ")
          + " " + [...bandPts].reverse()
            .map((p) => `L${x(p.date).toFixed(1)},${y(p.low_pct!).toFixed(1)}`).join(" ")
          + " Z"
        : "";
      const todayPct = line.series.find((p) => p.date === today)?.percent;
      const ideal = todayPct !== undefined && x(examDate) > x(today)
        ? `M${x(today).toFixed(1)},${y(todayPct).toFixed(1)} `
          + `L${x(examDate).toFixed(1)},${y(100).toFixed(1)}`
        : "";
      return {
        key: line.key,
        label: line.label,
        tone: line.tone,
        color: TONE_COLOR[line.tone],
        series: line.series,
        actual: actual.length > 1 ? seq(actual) : "",
        forecast: tail.length ? seq(forecast) : "",
        band,
        ideal,
        todayPct,
      };
    });

    const dates = [...new Set(pts.map((p) => p.date))].sort();
    const first = dates[0];
    const last = dates[dates.length - 1];
    const inRange = (iso: string) => x(iso) >= PAD.l - 1 && x(iso) <= W - PAD.r + 1;
    const marks: { date: string; anchor: "start" | "middle" | "end" }[] = [];
    const addMark = (date: string, anchor: "start" | "middle" | "end") => {
      if (!inRange(date)) return;
      if (marks.some((m) => Math.abs(x(m.date) - x(date)) < 46)) return;
      marks.push({ date, anchor });
    };
    addMark(first, "start");
    if (today !== first) addMark(today, "middle");
    if (examDate !== today) addMark(examDate, "middle");
    addMark(last, "end");

    const nearest = (px: number) => {
      let best = dates[0];
      let dist = Infinity;
      for (const d of dates) {
        const delta = Math.abs(x(d) - px);
        if (delta < dist) { dist = delta; best = d; }
      }
      return best;
    };

    return { paths, yMax, y, x, marks, first, last, dates, nearest, inRange };
  }, [lines, examDate, today, height]);

  if (!geo) return null;
  const { paths, yMax, y, x, marks, dates, nearest, inRange } = geo;
  const ticks = yMax <= 100 ? [0, 50, 100] : [0, Math.round(yMax / 2), yMax];
  const activeRows = active
    ? paths.map((p) => ({ ...p, point: pointAt(p.series, active) }))
    : [];

  const pick = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    setActive(nearest(((e.clientX - rect.left) / rect.width) * W));
  };

  const move = (dir: 1 | -1) => {
    const base = active ? dates.indexOf(active) : Math.max(0, dates.indexOf(today));
    setActive(dates[Math.max(0, Math.min(dates.length - 1, base + dir))]);
  };

  const tipW = 172;
  const tipH = 24 + paths.length * 17;
  const activeX = active ? x(active) : 0;
  const tipX = activeX + tipW + 12 > W - PAD.r ? activeX - tipW - 12 : activeX + 12;
  const tipY = PAD.t + 4;

  return (
    <>
      <svg viewBox={`0 0 ${W} ${height}`} className="progress-chart" role="img"
        tabIndex={0} aria-label={summary ?? "记与听的学习进度曲线与预测"}
        onPointerMove={pick} onPointerDown={pick}
        onPointerLeave={() => setActive(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") { e.preventDefault(); move(-1); }
          else if (e.key === "ArrowRight") { e.preventDefault(); move(1); }
          else if (e.key === "Escape") setActive(null);
        }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)}
              stroke="var(--line)" strokeWidth="1" />
            <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" className="pc-axis">{t}%</text>
          </g>
        ))}

        <line x1={PAD.l} x2={W - PAD.r} y1={y(100)} y2={y(100)}
          stroke="var(--chart-goal)" strokeWidth="1" strokeDasharray="5 5" opacity=".7" />

        {inRange(examDate) && (
          <line x1={x(examDate)} x2={x(examDate)} y1={PAD.t} y2={height - PAD.b}
            stroke="var(--chart-goal)" strokeWidth="1" strokeDasharray="3 4" opacity=".7" />
        )}

        {paths.map((p) => p.band && (
          <path key={`b-${p.key}`} d={p.band} fill={p.color} opacity=".12" />
        ))}
        {paths.map((p) => p.ideal && (
          <path key={`i-${p.key}`} d={p.ideal} fill="none" stroke={p.color}
            strokeWidth="1" strokeDasharray="2 5" opacity=".45" />
        ))}
        {paths.map((p) => p.forecast && (
          <path key={`f-${p.key}`} d={p.forecast} fill="none" stroke={p.color}
            strokeWidth="2.2" strokeLinecap="round" strokeDasharray={DASH[p.tone]} opacity=".85" />
        ))}
        {paths.map((p) => p.actual && (
          <path key={`a-${p.key}`} d={p.actual} fill="none" stroke={p.color}
            strokeWidth="2.8" strokeLinecap="round" />
        ))}
        {paths.map((p) => p.todayPct !== undefined && (
          <circle key={`t-${p.key}`} cx={x(today)} cy={y(p.todayPct)} r="4.5"
            fill={p.color} stroke="var(--card-strong)" strokeWidth={p.tone === "memo" ? 2 : 3} />
        ))}

        {marks.map((m) => (
          <text key={m.date} x={x(m.date)} y={height - 8} textAnchor={m.anchor}
            className="pc-axis">{md(m.date)}</text>
        ))}

        {active && (
          <g className="pc-tip">
            <line x1={x(active)} x2={x(active)} y1={PAD.t} y2={height - PAD.b}
              stroke="var(--muted)" strokeWidth="1" opacity=".5" />
            <rect x={tipX} y={tipY} width={tipW} height={tipH} rx="8"
              fill="var(--card-strong)" stroke="var(--line)" />
            <text x={tipX + 8} y={tipY + 16} className="pc-tip-date">{active}</text>
            {activeRows.map((r, i) => (
              <text key={r.key} x={tipX + 8} y={tipY + 33 + i * 17} className="pc-tip-row">
                {r.label} {r.point ? `${r.point.percent.toFixed(1)}%` : "—"}
                {r.point && !r.point.actual && r.point.low_pct !== undefined
                  ? `（${r.point.low_pct}–${r.point.high_pct}%）` : ""}
              </text>
            ))}
          </g>
        )}
      </svg>

      <details className="chart-table">
        <summary>查看数据表</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">日期</th>
              {lines.map((l) => <th key={l.key} scope="col">{l.label}</th>)}
              <th scope="col">预测区间</th>
            </tr>
          </thead>
          <tbody>
            {dates.map((d) => (
              <tr key={d}>
                <th scope="row">{d}</th>
                {lines.map((l) => {
                  const p = pointAt(l.series, d);
                  return <td key={l.key}>{p ? `${p.percent.toFixed(1)}%` : "—"}</td>;
                })}
                <td>
                  {lines.map((l) => {
                    const p = pointAt(l.series, d);
                    return p && !p.actual && p.low_pct !== undefined
                      ? `${l.label} ${p.low_pct}–${p.high_pct}% `
                      : "";
                  }).join("") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

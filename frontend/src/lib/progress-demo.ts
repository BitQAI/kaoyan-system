import type { SeriesPoint, SubjectLine, Timeline, DimStat } from "./progress-types";

const iso = (d: Date) => d.toISOString().slice(0, 10);
const pct = (done: number, total: number) => (total ? +((done / total) * 100).toFixed(2) : 0);
const DAY = 864e5;

function demoDim(label: string, total: number, pace: number, today: Date, exam: Date): DimStat {
  const series: SeriesPoint[] = [];
  let acc = 0;
  const hist = 20;
  for (let i = hist; i >= 0; i--) {
    const d = new Date(today.getTime() - i * DAY);
    if (i < hist) acc += pace;
    series.push({ date: iso(d), done: acc, percent: pct(acc, total), actual: true });
  }
  const finish = new Date(today.getTime() + Math.ceil((total - acc) / pace) * DAY);
  const end = Math.min(finish.getTime(), exam.getTime());
  for (let t = today.getTime() + DAY; t <= end; t += DAY) {
    const n = Math.min(total, acc + Math.round(pace * ((t - today.getTime()) / DAY)));
    const p = pct(n, total);
    series.push({
      date: iso(new Date(t)), done: n, percent: p, actual: false,
      low_pct: Math.max(0, +(p - 2).toFixed(2)),
      high_pct: Math.min(100, +(p + 2).toFixed(2)),
    });
  }
  const left = Math.max(1, Math.round((exam.getTime() - today.getTime()) / DAY));
  const earliest = new Date(finish.getTime() - 3 * DAY);
  const latest = new Date(Math.min(exam.getTime(), finish.getTime() + 5 * DAY));
  return {
    label, unit: "张", total, done: acc, percent: pct(acc, total),
    status: "ok", status_text: "按当前速度可以在初试前学完",
    pace, pace_window: 28, pace_trend: "flat",
    required_pace: +((total - acc) / left).toFixed(2),
    finish_date: iso(finish),
    finish_earliest: iso(earliest),
    finish_latest: iso(latest),
    mode: "load_aware", confidence: "high",
    capacity: { daily_actions: 30, review_load: 18, new_pace: pace },
    series,
    data_quality: { derived_cards: 0, recorded_cards: acc },
  };
}

function demoSubject(id: string, name: string, total: number, memoRate: number,
                     listenRate: number, exam: string): SubjectLine {
  const examDate = new Date(`${exam}T00:00:00Z`);
  const dim = (rate: number) => {
    const done = Math.round(total * rate);
    const pace = Math.max(1, Math.ceil((total - done) / 45));
    return {
      total, done, percent: pct(done, total), pace,
      finish_date: iso(new Date(examDate.getTime() - DAY)),
      finish_earliest: iso(new Date(examDate.getTime() - 5 * DAY)),
      finish_latest: exam,
      status: "ok" as const,
      mode: "linear" as const,
      confidence: "high" as const,
    };
  };
  return { id, name, memo: dim(memoRate), listen: dim(listenRate) };
}

export function demoData(): Timeline {
  const today = new Date();
  const examDate = new Date(today.getTime() + 51 * DAY);
  const examIso = iso(examDate);
  return {
    today: iso(today), exam_date: examIso, days_left: 51, scope: "all",
    dimensions: {
      memo: demoDim("记", 3171, 60, today, examDate),
      listen: demoDim("听", 3171, 52, today, examDate),
    },
    subjects: [
      demoSubject("812", "812 植物生理学", 780, 0.57, 0.44, examIso),
      demoSubject("315", "315 化学（农）", 1120, 0.33, 0.26, examIso),
      demoSubject("101", "101 思想政治理论", 870, 0.2, 0.18, examIso),
      demoSubject("204", "204 英语（二）", 401, 0.75, 0.61, examIso),
    ],
    review_load: { due_today: 42, steady_load: 18 },
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

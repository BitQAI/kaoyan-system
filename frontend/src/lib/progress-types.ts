export type DimStatus = "ok" | "risk" | "late" | "empty" | "insufficient" | "stalled";
export type PaceTrend = "up" | "down" | "flat";
export type ForecastMode = "load_aware" | "linear";
export type Confidence = "high" | "medium" | "low";
export type FocusMode = "memo" | "listen" | "both";

export interface SeriesPoint {
  date: string;
  done: number;
  percent: number;
  actual: boolean;
  low_pct?: number;
  high_pct?: number;
}

export interface ChartLine {
  key: string;
  label: string;
  tone: "memo" | "listen";
  series: SeriesPoint[];
}

export interface Capacity {
  daily_actions: number;
  review_load: number;
  new_pace: number;
}

export interface DimStat {
  label: string;
  unit: string;
  total: number;
  done: number;
  percent: number;
  status: DimStatus;
  status_text: string;
  pace: number;
  pace_window: number;
  pace_trend?: PaceTrend;
  required_pace: number | null;
  finish_date: string | null;
  finish_earliest?: string | null;
  finish_latest?: string | null;
  mode?: ForecastMode;
  confidence?: Confidence;
  capacity?: Capacity | null;
  series: SeriesPoint[];
  data_quality: { derived_cards: number; recorded_cards: number };
}

export interface SubjectDim {
  total: number;
  done: number;
  percent: number;
  pace: number;
  finish_date: string | null;
  status: DimStatus;
  finish_earliest?: string | null;
  finish_latest?: string | null;
  mode?: ForecastMode;
  confidence?: Confidence;
}

export interface SubjectLine {
  id: string;
  name: string;
  memo: SubjectDim;
  listen: SubjectDim;
}

export interface Milestones {
  count: number;
  items: { key: string; label: string }[];
  next: {
    label: string;
    current: number;
    target: number;
    kind: string;
    pct: number;
  } | null;
}

export interface Timeline {
  today: string;
  exam_date: string;
  days_left: number;
  scope: string;
  dimensions: { memo: DimStat; listen: DimStat };
  subjects: SubjectLine[];
  streak: number;
  daily: { goal: number; cards: number; listened: number; read: number };
  weekly: {
    this_week: number;
    last_week: number;
    delta_pct: number | null;
    week_start: string;
  };
  milestones: Milestones;
  review_load?: { due_today: number; steady_load: number };
}

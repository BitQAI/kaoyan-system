export type ViewMode = "listen" | "study" | "memo";

export interface Chapter {
  id: string;
  name: string;
  module: string;
  tier: number;
  weight_center: number;
  weight_range: number[] | null;
  weight_basis: "官方" | "推算" | "人工估计";
  entry_count: number;
  note?: string | null;
}

export interface Subject {
  id: string;
  name: string;
  score: number | null;
  status: string;
  chapters: Chapter[];
}

export interface PointIndex {
  id: string;
  chapter_id: string;
  subject_id: string;
  title: string;
  priority: string;
  evidence_level: "verified" | "inferred" | "pending";
}

export interface Manifest {
  subjects: Subject[];
  points: PointIndex[];
}

export interface Card {
  card_id: string;
  point_id: string;
  kind: string;
  card_type: string;
  question: string;
  answer: string;
  options: string[];
  answer_points: string[];
  analysis: string;
  unit_refs: number[];
  difficulty: number | null;
  priority?: string;
  title?: string;
  subject_id?: string;
  chapter_id?: string;
  due_at?: string | null;
  new?: boolean;
}

export interface Figure {
  kind: string;
  caption: string;
  alt: string;
  svg: string;
}

export interface RelationItem {
  point_id: string | null;
  name: string;
  distinction: string;
}

export interface PointDetail {
  id: string;
  subject_id: string;
  chapter_id: string;
  point: string;
  title: string;
  explain: string;
  exam: string;
  keywords: string[];
  priority: string;
  tags: string[];
  exam_types: string[];
  spoken: string;
  source: { ref: string | null; file: string | null; section: string | null; basis: string | null; kind: string | null };
  exam_evidence: { level: string; basis: string; sources: { id: string }[] };
  listen: { script: string; card_id: string | null; kind: string | null };
  tts: { enabled: boolean; est_sec: number | null };
  units: string[];
  cards: Card[];
  media: Figure[];
  relations: { prerequisite: RelationItem[]; related: RelationItem[]; confusable: RelationItem[] };
}

export interface ListenItem {
  card_id: string;
  point_id: string;
  subject_id: string;
  title: string;
  point: string;
  kind: string;
  card_type: string;
  /** 考点（卡片设问） */
  question: string;
  /** 真实作答（考试里该写/该说的那段话） */
  answer: string;
  /** 评分要点与注意事项，默认折叠、不朗读 */
  analysis: string;
  answer_points: string[];
  fallback: string;
  chapter_name: string;
  chapter_id: string;
  priority?: string;
  exam_types?: string[];
  heard: boolean;
  listen_count: number;
}

export interface ChapterProgress {
  id: string;
  name: string;
  module: string;
  sort: number;
  total: number;
  read_n: number;
  seen_n: number;
  card_n: number;
}

export interface ProgressStats {
  points: { total: number; read: number };
  cards: { total: number; seen: number; mastered: number; due: number };
  listen: { total: number; heard: number };
  today: { date: string; cards_seen: number; cards_due: number; listen_done: number; read_done: number };
  chapters: ChapterProgress[];
}

export interface HistoryItem {
  id: number;
  conversation_id: string;
  ts: string;
  question: string;
  answer: string;
  related_point_ids: string[];
}

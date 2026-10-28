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
  point_id: string;
  subject_id: string;
  title: string;
  point: string;
  script: string;
  kind: string | null;
  exam_types: string[];
  chapter_name: string;
  question: string | null;
  heard: boolean;
  listen_count: number;
}

export interface HistoryItem {
  id: number;
  conversation_id: string;
  ts: string;
  question: string;
  answer: string;
  related_point_ids: string[];
}

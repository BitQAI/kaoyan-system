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

export interface WordExample {
  /** 真题：能在语料中回溯到原句；例句：自写，卡面必须标注 */
  kind: "真题" | "例句";
  quote: string;
  cn?: string;
  year?: number;
  part?: string;
  text?: string;
  qno?: number;
  /** 该句在题里怎么被考 */
  tested?: string;
  note?: string;
}

export interface WordPayload {
  type: "word" | "phrase" | "confusable";
  /** 仅 word / phrase 类型有 */
  word?: string;
  phonetic?: string;
  meanings?: { pos: string; cn: string }[];
  examples?: WordExample[];
  confusables?: { word: string; diff: string }[];
  phrases?: { en: string; cn: string }[];
  /** 辨析卡 */
  group?: string[];
  stem?: string;
  answer?: string;
  diff?: string;
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
  /** 词卡 / 词组卡 / 辨析卡的结构化内容；其余题型为空对象 */
  payload?: WordPayload | Record<string, never>;
  priority?: string;
  /** 记过几次 / 上次评分 / 听过几次 */
  reviews?: number;
  last_result?: string | null;
  lapses?: number;
  listen_count?: number;
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
  /** 词卡/词组卡的结构化内容；其余题型为空对象 */
  payload?: WordPayload | Record<string, never>;
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
  reviews?: number;
  last_result?: string | null;
  lapses?: number;
  due_at?: string | null;
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

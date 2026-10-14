CREATE TABLE IF NOT EXISTS progress (
  point_id   TEXT PRIMARY KEY,
  state      TEXT NOT NULL DEFAULT 'new',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_pos (
  clip_id      TEXT PRIMARY KEY,
  position_sec REAL NOT NULL DEFAULT 0,
  plays        INTEGER NOT NULL DEFAULT 0,
  last_at      TEXT
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  quiz_id  TEXT NOT NULL,
  chosen   INTEGER,
  correct  INTEGER NOT NULL,
  ts       TEXT NOT NULL,
  response TEXT
);

CREATE TABLE IF NOT EXISTS wrong_book (
  quiz_id       TEXT PRIMARY KEY,
  wrong_count   INTEGER NOT NULL DEFAULT 1,
  streak        INTEGER NOT NULL DEFAULT 0,
  resolved_at   TEXT,
  last_wrong_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
  type       TEXT NOT NULL,
  ref_id     TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (type, ref_id)
);

CREATE TABLE IF NOT EXISTS ai_threads (
  id         TEXT PRIMARY KEY,
  owner_type TEXT NOT NULL,
  owner_ref  TEXT,
  title      TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_messages (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id TEXT NOT NULL REFERENCES ai_threads(id),
  role      TEXT NOT NULL,
  content   TEXT NOT NULL,
  reasoning TEXT,
  ts        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_log (
  date       TEXT PRIMARY KEY,
  listen_sec INTEGER NOT NULL DEFAULT 0,
  clips      INTEGER NOT NULL DEFAULT 0,
  cards      INTEGER NOT NULL DEFAULT 0,
  quiz_n     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
  point_id   TEXT PRIMARY KEY,
  stage      INTEGER NOT NULL DEFAULT 0,
  due_date   TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_runs (
  id          TEXT PRIMARY KEY,
  subject     TEXT NOT NULL,
  kind        TEXT NOT NULL,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  detail_json TEXT NOT NULL,
  score       REAL,
  total       REAL
);

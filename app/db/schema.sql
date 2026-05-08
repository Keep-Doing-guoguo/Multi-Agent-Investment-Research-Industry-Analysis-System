PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  title TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversation_turns_session_created
  ON conversation_turns (session_id, created_at);

CREATE TABLE IF NOT EXISTS session_summaries (
  session_id TEXT PRIMARY KEY,
  summary TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS structured_memories (
  session_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  research_topic TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  current_agent TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  recollect_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_session_created
  ON runs (session_id, created_at);

CREATE TABLE IF NOT EXISTS run_states (
  run_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  agent_name TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_run_events_run_created
  ON run_events (run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id
  ON run_events (run_id, event_id);

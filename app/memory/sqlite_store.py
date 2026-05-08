from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.sqlite3"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "app" / "db" / "schema.sql"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        schema_path: str | Path = DEFAULT_SCHEMA_PATH,
    ) -> None:
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        schema_sql = self.schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema_sql)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_session(self, session_id: str, title: str | None = None) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, title, status, created_at, updated_at)
                VALUES (?, ?, 'active', ?, ?)
                """,
                (session_id, title, now, now),
            )
            conn.execute(
                """
                INSERT INTO session_summaries (session_id, summary, updated_at)
                VALUES (?, '', ?)
                """,
                (session_id, now),
            )
            conn.execute(
                """
                INSERT INTO structured_memories (session_id, payload_json, updated_at)
                VALUES (?, '{}', ?)
                """,
                (session_id, now),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def insert_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = utc_now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO conversation_turns
                  (session_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, metadata_json, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            return int(cursor.lastrowid)

    def get_recent_turns(self, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, metadata_json, created_at
                FROM conversation_turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        turns = [self._decode_json_columns(row, ("metadata_json",)) for row in rows]
        return list(reversed(turns))

    def get_summary(self, session_id: str) -> str:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT summary FROM session_summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return str(row["summary"]) if row else ""

    def update_summary(self, session_id: str, summary: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE session_summaries
                SET summary = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (summary, now, session_id),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def get_structured_memory(self, session_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM structured_memories WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return {}
        return self._loads_json(row["payload_json"])

    def update_structured_memory(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        now = utc_now()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE structured_memories
                SET payload_json = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (payload_json, now, session_id),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def create_run(
        self,
        run_id: str,
        session_id: str,
        research_topic: str,
        status: str = "pending",
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs
                  (run_id, session_id, research_topic, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, session_id, research_topic, status, now, now),
            )
            conn.execute(
                """
                INSERT INTO run_states (run_id, payload_json, updated_at)
                VALUES (?, '{}', ?)
                """,
                (run_id, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_run_status(
        self,
        run_id: str,
        status: str,
        current_agent: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, current_agent = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, current_agent, now, run_id),
            )

    def increment_run_retry_count(self, run_id: str) -> int:
        return self._increment_run_counter(run_id, "retry_count")

    def increment_run_recollect_count(self, run_id: str) -> int:
        return self._increment_run_counter(run_id, "recollect_count")

    def get_run_state(self, run_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM run_states WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return {}
        return self._loads_json(row["payload_json"])

    def update_run_state(self, run_id: str, payload: dict[str, Any]) -> None:
        now = utc_now()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE run_states
                SET payload_json = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (payload_json, now, run_id),
            )
            conn.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )

    def insert_run_event(
        self,
        run_id: str,
        event_type: str,
        agent_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        now = utc_now()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO run_events
                  (run_id, event_type, agent_name, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, event_type, agent_name, payload_json, now),
            )
            conn.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )
            return int(cursor.lastrowid)

    def get_run_events(
        self,
        run_id: str,
        after_event_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT event_id, run_id, event_type, agent_name, payload_json, created_at
            FROM run_events
            WHERE run_id = ?
        """
        params: list[Any] = [run_id]
        if after_event_id is not None:
            query += " AND event_id > ?"
            params.append(after_event_id)
        query += " ORDER BY event_id ASC LIMIT ?"
        params.append(limit)

        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._decode_json_columns(row, ("payload_json",)) for row in rows]

    @staticmethod
    def _loads_json(value: str) -> dict[str, Any]:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}

    def _increment_run_counter(self, run_id: str, column: str) -> int:
        if column not in {"retry_count", "recollect_count"}:
            raise ValueError(f"Unsupported run counter: {column}")
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE runs
                SET {column} = {column} + 1, updated_at = ?
                WHERE run_id = ?
                """,
                (now, run_id),
            )
            row = conn.execute(
                f"SELECT {column} FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"Run not found: {run_id}")
        return int(row[column])

    @classmethod
    def _decode_json_columns(
        cls,
        row: sqlite3.Row,
        json_columns: tuple[str, ...],
    ) -> dict[str, Any]:
        item = dict(row)
        for column in json_columns:
            item[column.replace("_json", "")] = cls._loads_json(str(item.pop(column)))
        return item

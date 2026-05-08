from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.memory.sqlite_store import SQLiteStore


class SQLiteStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.store = SQLiteStore(db_path=self.db_path)
        self.store.init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_init_db_creates_expected_tables(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()

        table_names = {row[0] for row in rows}
        self.assertTrue(
            {
                "sessions",
                "conversation_turns",
                "session_summaries",
                "structured_memories",
                "runs",
                "run_states",
                "run_events",
            }.issubset(table_names)
        )

    def test_session_creation_initializes_memory_rows(self) -> None:
        self.store.create_session("session_1", title="Demo")

        session = self.store.get_session("session_1")
        summary = self.store.get_summary("session_1")
        structured_memory = self.store.get_structured_memory("session_1")

        self.assertEqual(session["session_id"], "session_1")
        self.assertEqual(session["title"], "Demo")
        self.assertEqual(summary, "")
        self.assertEqual(structured_memory, {})

    def test_turns_are_returned_in_chronological_order(self) -> None:
        self.store.create_session("session_1")
        self.store.insert_turn("session_1", "user", "query 1")
        self.store.insert_turn("session_1", "assistant", "response 1")
        self.store.insert_turn("session_1", "user", "query 2")

        recent_turns = self.store.get_recent_turns("session_1", limit=2)

        self.assertEqual([turn["content"] for turn in recent_turns], ["response 1", "query 2"])

    def test_run_state_and_events_round_trip(self) -> None:
        self.store.create_session("session_1")
        self.store.create_run("run_1", "session_1", "新能源汽车行业")
        self.store.update_run_state("run_1", {"current_step": "triage"})
        event_id = self.store.insert_run_event(
            "run_1",
            "agent_started",
            agent_name="TriageAgent",
            payload={"message": "start"},
        )

        run = self.store.get_run("run_1")
        run_state = self.store.get_run_state("run_1")
        events = self.store.get_run_events("run_1")
        events_after_first = self.store.get_run_events("run_1", after_event_id=event_id)

        self.assertEqual(run["research_topic"], "新能源汽车行业")
        self.assertEqual(run_state, {"current_step": "triage"})
        self.assertEqual(events[0]["event_type"], "agent_started")
        self.assertEqual(events[0]["payload"], {"message": "start"})
        self.assertEqual(events_after_first, [])


if __name__ == "__main__":
    unittest.main()

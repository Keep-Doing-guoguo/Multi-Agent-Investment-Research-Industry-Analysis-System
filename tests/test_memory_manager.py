from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore


class MemoryManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.manager = MemoryManager(
            store=SQLiteStore(db_path=self.db_path),
            recent_turns_limit=2,
        )
        self.manager.init_db()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_patch_structured_memory_appends_unique_list_items(self) -> None:
        session_id = self.manager.create_session("Demo")

        first = self.manager.patch_structured_memory(
            session_id,
            {
                "risk_focus": ["价格战"],
                "user_preferences": ["结论谨慎"],
            },
        )
        second = self.manager.patch_structured_memory(
            session_id,
            {
                "risk_focus": ["价格战", "出口增长"],
            },
        )

        self.assertEqual(first["risk_focus"], ["价格战"])
        self.assertEqual(second["risk_focus"], ["价格战", "出口增长"])
        self.assertEqual(second["user_preferences"], ["结论谨慎"])

    def test_patch_run_state_merges_nested_dicts(self) -> None:
        session_id = self.manager.create_session("Demo")
        run_id = self.manager.create_run(
            session_id,
            research_topic="新能源汽车行业",
            request={"query": "分析新能源汽车行业"},
        )

        updated = self.manager.patch_run_state(
            run_id,
            {
                "current_step": "triage",
                "triage_result": {
                    "research_type": "industry_analysis",
                },
            },
        )

        self.assertEqual(updated["current_step"], "triage")
        self.assertEqual(updated["request"], {"query": "分析新能源汽车行业"})
        self.assertEqual(
            updated["triage_result"],
            {"research_type": "industry_analysis"},
        )

    def test_build_context_for_agent_returns_session_memory_and_run_state(self) -> None:
        session_id = self.manager.create_session("Demo")
        self.manager.append_turn(session_id, "user", "query 1")
        self.manager.append_turn(session_id, "assistant", "response 1")
        self.manager.append_turn(session_id, "user", "query 2")
        self.manager.update_summary(session_id, "用户正在研究新能源汽车行业。")
        self.manager.patch_structured_memory(
            session_id,
            {"risk_focus": ["价格战"]},
        )
        run_id = self.manager.create_run(
            session_id,
            research_topic="新能源汽车行业",
            request={"query": "query 2"},
        )

        context = self.manager.build_context_for_agent(
            session_id,
            run_id,
            "TriageAgent",
        )

        self.assertEqual(context["agent_name"], "TriageAgent")
        self.assertEqual(context["conversation_summary"], "用户正在研究新能源汽车行业。")
        self.assertEqual(context["structured_memory"], {"risk_focus": ["价格战"]})
        self.assertEqual(
            [turn["content"] for turn in context["recent_turns"]],
            ["response 1", "query 2"],
        )
        self.assertEqual(context["run_state"]["request"], {"query": "query 2"})

    def test_emit_run_event_records_sse_ready_event(self) -> None:
        session_id = self.manager.create_session("Demo")
        run_id = self.manager.create_run(session_id, "新能源汽车行业")

        self.manager.emit_run_event(
            run_id,
            event_type="agent_started",
            agent_name="TriageAgent",
            payload={"message": "start"},
        )

        events = self.manager.get_run_events(run_id)

        self.assertEqual(events[0]["event_type"], "run_created")
        self.assertEqual(events[1]["event_type"], "agent_started")
        self.assertEqual(events[1]["agent_name"], "TriageAgent")
        self.assertEqual(events[1]["payload"], {"message": "start"})


if __name__ == "__main__":
    unittest.main()

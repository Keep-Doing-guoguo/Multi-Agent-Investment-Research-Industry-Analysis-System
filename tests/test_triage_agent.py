from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.agents.triage_agent import TriageAgent
from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import (
    ResearchDirection,
    ResearchType,
    TriageOutput,
)
from app.tools.mock_research_tools import build_default_tool_registry


T = TypeVar("T", bound=BaseModel)


class FakeLLMClient:
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        output = TriageOutput(
            agent_name="TriageAgent",
            summary="识别为新能源汽车行业分析任务",
            research_type=ResearchType.INDUSTRY_ANALYSIS,
            target="中国新能源汽车行业",
            directions=[
                ResearchDirection(
                    name="竞争格局",
                    reason="用户需要行业分析，需要比较主要参与者",
                ),
                ResearchDirection(
                    name="风险因素",
                    reason="用户关注价格战和产能过剩",
                ),
            ],
            constraints=["结论谨慎"],
            required_tools=["news_search", "industry_data_search"],
        )
        return output_model.model_validate(output.to_dict())


class TriageAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.memory = MemoryManager(SQLiteStore(db_path=db_path))
        self.memory.init_db()
        self.tools = build_default_tool_registry()
        self.llm = FakeLLMClient()
        self.agent = TriageAgent(self.memory, self.llm, self.tools)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_triage_agent_updates_memory_run_state_and_events(self) -> None:
        session_id = self.memory.create_session("Demo")
        self.memory.append_turn(
            session_id,
            "user",
            "帮我分析中国新能源汽车行业，结论要谨慎。",
        )
        run_id = self.memory.create_run(
            session_id,
            research_topic="中国新能源汽车行业",
            request={"query": "帮我分析中国新能源汽车行业，结论要谨慎。"},
        )

        output = self.agent.run(session_id=session_id, run_id=run_id)

        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        structured_memory = self.memory.get_structured_memory(session_id)
        events = self.memory.get_run_events(run_id)

        self.assertEqual(output.research_type, "industry_analysis")
        self.assertEqual(run["status"], "running")
        self.assertEqual(run["current_agent"], "TriageAgent")
        self.assertEqual(run_state["current_step"], "triage_completed")
        self.assertEqual(
            run_state["triage_result"]["required_tools"],
            ["news_search", "industry_data_search"],
        )
        self.assertEqual(structured_memory["research_topic"], "中国新能源汽车行业")
        self.assertEqual(structured_memory["research_type"], "industry_analysis")
        self.assertEqual(structured_memory["research_constraints"], ["结论谨慎"])
        self.assertEqual(
            [event["event_type"] for event in events],
            ["run_created", "agent_started", "agent_completed"],
        )
        self.assertIn("available_tools", self.llm.user_prompt)


if __name__ == "__main__":
    unittest.main()

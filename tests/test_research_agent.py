from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.agents.research_agent import ResearchAgent
from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import ResearchOutput, SourceItem
from app.tools.mock_research_tools import build_default_tool_registry


T = TypeVar("T", bound=BaseModel)


class FakeResearchLLMClient:
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        output = ResearchOutput(
            agent_name="ResearchAgent",
            summary="已收集新闻和行业数据材料",
            sources=[
                SourceItem(
                    title="新能源汽车行业数据摘要",
                    source_type="industry_data",
                    published_at="2026-05-01",
                    summary="需求仍有增长空间，但竞争和产能压力需要关注。",
                )
            ],
            key_materials=["行业需求仍有增长空间", "竞争强度较高"],
            data_gaps=["缺少企业级盈利能力对比数据"],
        )
        return output_model.model_validate(output.to_dict())


class ResearchAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.memory = MemoryManager(SQLiteStore(db_path=db_path))
        self.memory.init_db()
        self.tools = build_default_tool_registry()
        self.llm = FakeResearchLLMClient()
        self.agent = ResearchAgent(self.memory, self.llm, self.tools)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_research_agent_executes_tools_and_updates_run_state(self) -> None:
        session_id = self.memory.create_session("Demo")
        run_id = self.memory.create_run(
            session_id,
            research_topic="中国新能源汽车行业",
            request={"query": "分析中国新能源汽车行业"},
        )
        self.memory.patch_run_state(
            run_id,
            {
                "triage_result": {
                    "target": "中国新能源汽车行业",
                    "directions": [
                        {"name": "竞争格局", "reason": "行业分析需要"},
                        {"name": "风险因素", "reason": "用户关注风险"},
                    ],
                    "constraints": ["结论谨慎"],
                    "required_tools": ["news_search", "industry_data_search"],
                }
            },
        )

        output = self.agent.run(session_id=session_id, run_id=run_id)

        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        events = self.memory.get_run_events(run_id)
        event_types = [event["event_type"] for event in events]

        self.assertEqual(output.agent_name, "ResearchAgent")
        self.assertEqual(run["current_agent"], "ResearchAgent")
        self.assertEqual(run_state["current_step"], "research_completed")
        self.assertEqual(
            run_state["research_result"]["key_materials"],
            ["行业需求仍有增长空间", "竞争强度较高"],
        )
        self.assertEqual(
            [result["tool_name"] for result in run_state["tool_results"]],
            ["news_search", "industry_data_search"],
        )
        self.assertEqual(
            event_types,
            [
                "run_created",
                "agent_started",
                "tool_started",
                "tool_completed",
                "tool_started",
                "tool_completed",
                "agent_completed",
            ],
        )
        self.assertIn("tool_results", self.llm.user_prompt)


if __name__ == "__main__":
    unittest.main()

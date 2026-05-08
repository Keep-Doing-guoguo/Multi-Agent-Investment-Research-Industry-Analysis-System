from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.agents.analysis_agent import AnalysisAgent
from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import AnalysisFinding, AnalysisOutput


T = TypeVar("T", bound=BaseModel)


class FakeAnalysisLLMClient:
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        output = AnalysisOutput(
            agent_name="AnalysisAgent",
            summary="行业仍有增长空间，但竞争压力较高。",
            findings=[
                AnalysisFinding(
                    claim="新能源汽车行业需求仍有增长空间",
                    evidence=["行业数据摘要显示需求增长为 moderate"],
                    confidence="medium",
                ),
                AnalysisFinding(
                    claim="价格竞争可能压制利润率",
                    evidence=["新闻摘要显示市场竞争加剧"],
                    confidence="medium",
                ),
            ],
            growth_drivers=["出口增长", "技术迭代"],
            risk_points=["价格战", "产能利用率压力"],
            draft_report="中国新能源汽车行业仍有增长空间，但价格竞争和产能压力需要谨慎评估。",
        )
        return output_model.model_validate(output.to_dict())


class AnalysisAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.memory = MemoryManager(SQLiteStore(db_path=db_path))
        self.memory.init_db()
        self.llm = FakeAnalysisLLMClient()
        self.agent = AnalysisAgent(self.memory, self.llm)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_analysis_agent_updates_run_state_with_analysis_output(self) -> None:
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
                    "research_type": "industry_analysis",
                },
                "research_result": {
                    "summary": "已收集新闻和行业数据材料",
                    "key_materials": ["行业需求仍有增长空间", "竞争强度较高"],
                    "data_gaps": ["缺少企业级盈利能力对比数据"],
                },
                "tool_results": [
                    {
                        "tool_name": "industry_data_search",
                        "items": [
                            {
                                "title": "行业数据摘要",
                                "summary": "需求仍有增长空间，但竞争压力较高。",
                            }
                        ],
                    }
                ],
            },
        )

        output = self.agent.run(session_id=session_id, run_id=run_id)

        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        events = self.memory.get_run_events(run_id)

        self.assertEqual(output.agent_name, "AnalysisAgent")
        self.assertEqual(run["current_agent"], "AnalysisAgent")
        self.assertEqual(run_state["current_step"], "analysis_completed")
        self.assertEqual(
            run_state["analysis_result"]["growth_drivers"],
            ["出口增长", "技术迭代"],
        )
        self.assertEqual(
            run_state["analysis_draft"],
            "中国新能源汽车行业仍有增长空间，但价格竞争和产能压力需要谨慎评估。",
        )
        self.assertEqual(
            [event["event_type"] for event in events],
            ["run_created", "agent_started", "agent_completed"],
        )
        self.assertIn("research_result", self.llm.user_prompt)
        self.assertIn("tool_results", self.llm.user_prompt)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.agents.risk_agent import RiskAgent
from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import RiskDecision, RiskFinding, RiskOutput, Severity


T = TypeVar("T", bound=BaseModel)


class FakeRiskLLMClient:
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        output = RiskOutput(
            agent_name="RiskAgent",
            summary="分析草稿有证据支撑，但仍需提示价格竞争风险。",
            decision=RiskDecision.PASS,
            findings=[
                RiskFinding(
                    finding_type="missing_risk",
                    severity=Severity.MEDIUM,
                    message="最终报告需要保留价格竞争对利润率的提示。",
                    suggested_action="在风险摘要中明确列出价格竞争风险。",
                    evidence_refs=["analysis_result.risk_points"],
                )
            ],
            reason="核心结论有资料支撑，风险点可以进入最终汇总。",
        )
        return output_model.model_validate(output.to_dict())


class RiskAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.memory = MemoryManager(SQLiteStore(db_path=db_path))
        self.memory.init_db()
        self.llm = FakeRiskLLMClient()
        self.agent = RiskAgent(self.memory, self.llm)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_risk_agent_updates_run_state_and_emits_decision(self) -> None:
        session_id = self.memory.create_session("Demo")
        run_id = self.memory.create_run(
            session_id,
            research_topic="中国新能源汽车行业",
            request={"query": "分析中国新能源汽车行业"},
        )
        self.memory.patch_run_state(
            run_id,
            {
                "research_result": {
                    "summary": "已收集新闻和行业数据材料",
                    "data_gaps": [],
                },
                "analysis_result": {
                    "summary": "行业仍有增长空间，但竞争压力较高。",
                    "risk_points": ["价格战"],
                },
                "analysis_draft": "中国新能源汽车行业仍有增长空间，但价格竞争需要谨慎评估。",
            },
        )

        output = self.agent.run(session_id=session_id, run_id=run_id)

        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        events = self.memory.get_run_events(run_id)

        self.assertEqual(output.decision, "pass")
        self.assertEqual(run["current_agent"], "RiskAgent")
        self.assertEqual(run_state["current_step"], "risk_completed")
        self.assertEqual(run_state["risk_decision"], "pass")
        self.assertEqual(run_state["decision"], "pass")
        self.assertEqual(
            run_state["risk_findings"][0]["message"],
            "最终报告需要保留价格竞争对利润率的提示。",
        )
        self.assertEqual(
            [event["event_type"] for event in events],
            ["run_created", "agent_started", "risk_decision", "agent_completed"],
        )
        self.assertIn("analysis_draft", self.llm.user_prompt)
        self.assertIn("research_result", self.llm.user_prompt)


if __name__ == "__main__":
    unittest.main()

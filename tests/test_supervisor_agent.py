from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.agents.supervisor_agent import SupervisorAgent
from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import SupervisorOutput


T = TypeVar("T", bound=BaseModel)


class FakeSupervisorLLMClient:
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        output = SupervisorOutput(
            agent_name="SupervisorAgent",
            summary="完成新能源汽车行业分析报告。",
            final_report="中国新能源汽车行业仍有增长空间，但价格竞争和产能压力需要持续跟踪。",
            key_conclusions=[
                "行业需求仍有增长空间",
                "价格竞争可能压制利润率",
            ],
            risk_summary=[
                "价格战风险",
                "产能利用率压力",
            ],
            follow_up_suggestions=[
                "跟踪月度销量和出口数据",
                "跟踪主要企业毛利率变化",
            ],
        )
        return output_model.model_validate(output.to_dict())


class SupervisorAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.memory = MemoryManager(SQLiteStore(db_path=db_path))
        self.memory.init_db()
        self.llm = FakeSupervisorLLMClient()
        self.agent = SupervisorAgent(self.memory, self.llm)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_supervisor_agent_completes_run_and_writes_final_report(self) -> None:
        session_id = self.memory.create_session("Demo")
        run_id = self.memory.create_run(
            session_id,
            research_topic="中国新能源汽车行业",
            request={"query": "分析中国新能源汽车行业"},
        )
        self.memory.patch_run_state(
            run_id,
            {
                "analysis_result": {
                    "summary": "行业仍有增长空间，但竞争压力较高。",
                    "risk_points": ["价格战"],
                },
                "analysis_draft": "中国新能源汽车行业仍有增长空间，但价格竞争需要谨慎评估。",
                "risk_result": {
                    "decision": "pass",
                    "findings": [],
                },
                "risk_findings": [],
            },
        )

        output = self.agent.run(session_id=session_id, run_id=run_id)

        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        structured_memory = self.memory.get_structured_memory(session_id)
        events = self.memory.get_run_events(run_id)

        self.assertEqual(output.agent_name, "SupervisorAgent")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["current_agent"], "SupervisorAgent")
        self.assertEqual(run_state["current_step"], "supervisor_completed")
        self.assertEqual(
            run_state["final_report"],
            "中国新能源汽车行业仍有增长空间，但价格竞争和产能压力需要持续跟踪。",
        )
        self.assertEqual(
            structured_memory["accepted_findings"],
            ["行业需求仍有增长空间", "价格竞争可能压制利润率"],
        )
        self.assertEqual(
            [event["event_type"] for event in events],
            ["run_created", "agent_started", "agent_completed", "run_completed"],
        )
        self.assertIn("risk_result", self.llm.user_prompt)
        self.assertIn("analysis_result", self.llm.user_prompt)


if __name__ == "__main__":
    unittest.main()

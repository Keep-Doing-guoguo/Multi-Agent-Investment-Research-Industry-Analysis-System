from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import (
    AnalysisOutput,
    ResearchOutput,
    RiskDecision,
    RiskOutput,
    SupervisorOutput,
    TriageOutput,
)
from app.workflow.runner import (
    LoopLimitExceededError,
    ResearchWorkflowRunner,
    WorkflowConfig,
)


class FakeTriageAgent:
    def run(self, session_id: str, run_id: str) -> TriageOutput:
        output = TriageOutput(
            agent_name="TriageAgent",
            summary="triage",
            research_type="industry_analysis",
            target="中国新能源汽车行业",
            required_tools=["news_search"],
        )
        MEMORY.patch_run_state(run_id, {"triage_result": output.to_dict()})
        return output


class FakeResearchAgent:
    calls = 0

    def run(self, session_id: str, run_id: str) -> ResearchOutput:
        self.calls += 1
        output = ResearchOutput(
            agent_name="ResearchAgent",
            summary="research",
            key_materials=["material"],
        )
        MEMORY.patch_run_state(run_id, {"research_result": output.to_dict()})
        return output


class FakeAnalysisAgent:
    calls = 0

    def run(self, session_id: str, run_id: str) -> AnalysisOutput:
        self.calls += 1
        output = AnalysisOutput(
            agent_name="AnalysisAgent",
            summary="analysis",
            draft_report="analysis draft",
        )
        MEMORY.patch_run_state(
            run_id,
            {"analysis_result": output.to_dict(), "analysis_draft": output.draft_report},
        )
        return output


class FakeRiskAgent:
    def __init__(self, decisions: list[RiskDecision]) -> None:
        self.decisions = decisions
        self.index = 0

    def run(self, session_id: str, run_id: str) -> RiskOutput:
        decision = self.decisions[min(self.index, len(self.decisions) - 1)]
        self.index += 1
        output = RiskOutput(
            agent_name="RiskAgent",
            summary="risk",
            decision=decision,
            reason=f"decision={decision}",
        )
        MEMORY.patch_run_state(
            run_id,
            {
                "risk_result": output.to_dict(),
                "risk_decision": output.decision,
                "decision": output.decision,
            },
        )
        return output


class FakeSupervisorAgent:
    def run(self, session_id: str, run_id: str) -> SupervisorOutput:
        output = SupervisorOutput(
            agent_name="SupervisorAgent",
            summary="final",
            final_report="final report",
            key_conclusions=["conclusion"],
        )
        MEMORY.patch_run_state(
            run_id,
            {"supervisor_result": output.to_dict(), "final_report": output.final_report},
        )
        MEMORY.update_run_status(run_id, "completed", "SupervisorAgent")
        MEMORY.emit_run_event(run_id, "run_completed", "SupervisorAgent", {})
        return output


MEMORY: MemoryManager


class WorkflowRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        global MEMORY
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        MEMORY = MemoryManager(SQLiteStore(db_path=db_path))
        MEMORY.init_db()
        self.session_id = MEMORY.create_session("Demo")
        self.run_id = MEMORY.create_run(
            self.session_id,
            "中国新能源汽车行业",
            {"query": "分析中国新能源汽车行业"},
        )
        self.research_agent = FakeResearchAgent()
        self.analysis_agent = FakeAnalysisAgent()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def build_runner(self, risk_agent: FakeRiskAgent, config: WorkflowConfig | None = None) -> ResearchWorkflowRunner:
        return ResearchWorkflowRunner(
            memory=MEMORY,
            triage_agent=FakeTriageAgent(),
            research_agent=self.research_agent,
            analysis_agent=self.analysis_agent,
            risk_agent=risk_agent,
            supervisor_agent=FakeSupervisorAgent(),
            config=config,
        )

    def test_runner_completes_on_pass(self) -> None:
        runner = self.build_runner(FakeRiskAgent([RiskDecision.PASS]))

        result = runner.run(self.session_id, self.run_id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_report, "final report")
        self.assertEqual(result.steps_executed, 5)
        self.assertEqual(MEMORY.get_run(self.run_id)["retry_count"], 0)
        self.assertEqual(MEMORY.get_run(self.run_id)["recollect_count"], 0)

    def test_runner_retries_analysis_then_completes(self) -> None:
        runner = self.build_runner(
            FakeRiskAgent([RiskDecision.RETRY, RiskDecision.PASS])
        )

        result = runner.run(self.session_id, self.run_id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(MEMORY.get_run(self.run_id)["retry_count"], 1)
        self.assertEqual(self.analysis_agent.calls, 2)

    def test_runner_recollects_research_then_completes(self) -> None:
        runner = self.build_runner(
            FakeRiskAgent([RiskDecision.RECOLLECT, RiskDecision.PASS])
        )

        result = runner.run(self.session_id, self.run_id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(MEMORY.get_run(self.run_id)["recollect_count"], 1)
        self.assertEqual(self.research_agent.calls, 2)

    def test_runner_marks_run_failed_when_retry_limit_exceeded(self) -> None:
        runner = self.build_runner(
            FakeRiskAgent([RiskDecision.RETRY, RiskDecision.RETRY]),
            WorkflowConfig(max_retry_count=1, max_total_steps=10),
        )

        with self.assertRaises(LoopLimitExceededError):
            runner.run(self.session_id, self.run_id)

        run = MEMORY.get_run(self.run_id)
        run_state = MEMORY.get_run_state(self.run_id)
        events = MEMORY.get_run_events(self.run_id)

        self.assertEqual(run["status"], "failed")
        self.assertEqual(run_state["current_step"], "workflow_failed")
        self.assertEqual(events[-1]["event_type"], "run_failed")


if __name__ == "__main__":
    unittest.main()

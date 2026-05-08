from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.memory.manager import MemoryManager
from app.models.agent_outputs import (
    AnalysisOutput,
    ResearchOutput,
    RiskDecision,
    RiskOutput,
    SupervisorOutput,
    TriageOutput,
)


class TriageAgentLike(Protocol):
    def run(self, session_id: str, run_id: str) -> TriageOutput:
        ...


class ResearchAgentLike(Protocol):
    def run(self, session_id: str, run_id: str) -> ResearchOutput:
        ...


class AnalysisAgentLike(Protocol):
    def run(self, session_id: str, run_id: str) -> AnalysisOutput:
        ...


class RiskAgentLike(Protocol):
    def run(self, session_id: str, run_id: str) -> RiskOutput:
        ...


class SupervisorAgentLike(Protocol):
    def run(self, session_id: str, run_id: str) -> SupervisorOutput:
        ...


@dataclass(frozen=True)
class WorkflowConfig:
    max_retry_count: int = 2
    max_recollect_count: int = 2
    max_total_steps: int = 10


@dataclass(frozen=True)
class WorkflowResult:
    session_id: str
    run_id: str
    status: str
    final_report: str
    steps_executed: int


class WorkflowError(Exception):
    pass


class LoopLimitExceededError(WorkflowError):
    pass


class ResearchWorkflowRunner:
    def __init__(
        self,
        *,
        memory: MemoryManager,
        triage_agent: TriageAgentLike,
        research_agent: ResearchAgentLike,
        analysis_agent: AnalysisAgentLike,
        risk_agent: RiskAgentLike,
        supervisor_agent: SupervisorAgentLike,
        config: WorkflowConfig | None = None,
    ) -> None:
        self.memory = memory
        self.triage_agent = triage_agent
        self.research_agent = research_agent
        self.analysis_agent = analysis_agent
        self.risk_agent = risk_agent
        self.supervisor_agent = supervisor_agent
        self.config = config or WorkflowConfig()

    def run(self, session_id: str, run_id: str) -> WorkflowResult:
        current_node = "triage"
        steps_executed = 0

        try:
            while steps_executed < self.config.max_total_steps:
                steps_executed += 1
                self.memory.patch_run_state(
                    run_id,
                    {
                        "workflow_current_node": current_node,
                        "workflow_steps_executed": steps_executed,
                    },
                )

                if current_node == "triage":
                    self.triage_agent.run(session_id, run_id)
                    current_node = "research"
                elif current_node == "research":
                    self.research_agent.run(session_id, run_id)
                    current_node = "analysis"
                elif current_node == "analysis":
                    self.analysis_agent.run(session_id, run_id)
                    current_node = "risk"
                elif current_node == "risk":
                    self.risk_agent.run(session_id, run_id)
                    current_node = self._next_node_after_risk(run_id)
                elif current_node == "supervisor":
                    self.supervisor_agent.run(session_id, run_id)
                    return self._build_result(session_id, run_id, steps_executed)
                else:
                    raise WorkflowError(f"Unknown workflow node: {current_node}")

            raise LoopLimitExceededError(
                f"Workflow exceeded max_total_steps={self.config.max_total_steps}"
            )
        except Exception as exc:
            self._mark_failed(run_id, exc)
            raise

    def _next_node_after_risk(self, run_id: str) -> str:
        run_state = self.memory.get_run_state(run_id)
        decision = run_state.get("risk_decision") or run_state.get("decision")

        if decision == RiskDecision.PASS or decision == RiskDecision.PASS.value:
            return "supervisor"
        if decision == RiskDecision.RETRY or decision == RiskDecision.RETRY.value:
            retry_count = self.memory.increment_run_retry_count(run_id)
            if retry_count > self.config.max_retry_count:
                raise LoopLimitExceededError(
                    f"Retry limit exceeded: {retry_count}>{self.config.max_retry_count}"
                )
            self.memory.emit_run_event(
                run_id,
                event_type="workflow_retry",
                payload={"retry_count": retry_count, "next_node": "analysis"},
            )
            return "analysis"
        if decision == RiskDecision.RECOLLECT or decision == RiskDecision.RECOLLECT.value:
            recollect_count = self.memory.increment_run_recollect_count(run_id)
            if recollect_count > self.config.max_recollect_count:
                raise LoopLimitExceededError(
                    "Recollect limit exceeded: "
                    f"{recollect_count}>{self.config.max_recollect_count}"
                )
            self.memory.emit_run_event(
                run_id,
                event_type="workflow_recollect",
                payload={"recollect_count": recollect_count, "next_node": "research"},
            )
            return "research"

        raise WorkflowError(f"Unsupported risk decision: {decision}")

    def _build_result(
        self,
        session_id: str,
        run_id: str,
        steps_executed: int,
    ) -> WorkflowResult:
        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        return WorkflowResult(
            session_id=session_id,
            run_id=run_id,
            status=run["status"],
            final_report=run_state.get("final_report", ""),
            steps_executed=steps_executed,
        )

    def _mark_failed(self, run_id: str, exc: Exception) -> None:
        error_payload = {
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        run_state = self.memory.get_run_state(run_id)
        errors = list(run_state.get("errors", []))
        errors.append(error_payload)
        self.memory.patch_run_state(
            run_id,
            {
                "current_step": "workflow_failed",
                "errors": errors,
            },
        )
        self.memory.update_run_status(run_id, status="failed", current_agent=None)
        self.memory.emit_run_event(
            run_id,
            event_type="run_failed",
            payload=error_payload,
        )

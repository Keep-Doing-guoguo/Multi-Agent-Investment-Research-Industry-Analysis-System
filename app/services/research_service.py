from __future__ import annotations

from dataclasses import asdict
import json
import time
from typing import Any

from app.memory.manager import MemoryManager
from app.workflow.runner import ResearchWorkflowRunner, WorkflowResult


class ResearchService:
    def __init__(
        self,
        *,
        memory: MemoryManager,
        workflow_runner: ResearchWorkflowRunner,
    ) -> None:
        self.memory = memory
        self.workflow_runner = workflow_runner

    def create_and_run(
        self,
        *,
        query: str,
        topic: str,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if session_id is None:
            session_id = self.memory.create_session(title or topic)
        else:
            self.memory.get_session(session_id)
        self.memory.append_turn(session_id, "user", query)
        run_id = self.memory.create_run(
            session_id=session_id,
            research_topic=topic,
            request={"query": query},
        )
        result = self.execute_run(session_id=session_id, run_id=run_id)
        return self._build_run_payload(result.run_id, workflow_result=result)

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        session_id = self.memory.create_session(title)
        return self.memory.get_session(session_id)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.memory.get_session(session_id)

    def create_run_for_session(
        self,
        *,
        session_id: str,
        query: str,
        topic: str | None = None,
    ) -> dict[str, Any]:
        session = self.memory.get_session(session_id)
        research_topic = topic or session.get("title") or query
        self.memory.append_turn(session_id, "user", query)
        run_id = self.memory.create_run(
            session_id=session_id,
            research_topic=research_topic,
            request={"query": query},
        )
        return self._build_run_payload(run_id)

    def execute_run(self, *, session_id: str, run_id: str) -> WorkflowResult:
        result = self.workflow_runner.run(session_id=session_id, run_id=run_id)
        if result.final_report:
            self.memory.append_turn(
                session_id,
                "assistant",
                result.final_report,
                metadata={"run_id": run_id},
            )
        return result

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._build_run_payload(run_id)

    def get_run_result(self, run_id: str) -> dict[str, Any]:
        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        return {
            "run_id": run_id,
            "session_id": run["session_id"],
            "status": run["status"],
            "final_report": run_state.get("final_report", ""),
            "supervisor_result": run_state.get("supervisor_result", {}),
            "risk_findings": run_state.get("risk_findings", []),
        }

    def get_run_events(
        self,
        *,
        run_id: str,
        after_event_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.memory.get_run_events(
            run_id=run_id,
            after_event_id=after_event_id,
            limit=limit,
        )

    def stream_run_events(
        self,
        *,
        run_id: str,
        after_event_id: int | None = None,
        poll_interval_seconds: float = 1.0,
        max_idle_polls: int = 30,
    ):
        self.memory.get_run(run_id)
        last_event_id = after_event_id or 0
        idle_polls = 0

        while True:
            events = self.get_run_events(
                run_id=run_id,
                after_event_id=last_event_id,
                limit=100,
            )
            if events:
                idle_polls = 0
                for event in events:
                    last_event_id = event["event_id"]
                    yield format_sse_event(
                        event_type=event["event_type"],
                        event_id=event["event_id"],
                        data=event,
                    )
            else:
                idle_polls += 1
                yield ": keep-alive\n\n"

            run = self.memory.get_run(run_id)
            if run["status"] in {"completed", "failed", "cancelled"} and not events:
                break
            if idle_polls >= max_idle_polls:
                break

            time.sleep(poll_interval_seconds)

    def _build_run_payload(
        self,
        run_id: str,
        workflow_result: WorkflowResult | None = None,
    ) -> dict[str, Any]:
        run = self.memory.get_run(run_id)
        run_state = self.memory.get_run_state(run_id)
        payload = {
            "run_id": run_id,
            "session_id": run["session_id"],
            "research_topic": run["research_topic"],
            "status": run["status"],
            "current_agent": run["current_agent"],
            "retry_count": run["retry_count"],
            "recollect_count": run["recollect_count"],
            "state": run_state,
        }
        if workflow_result:
            payload["workflow"] = asdict(workflow_result)
        return payload


def format_sse_event(
    *,
    event_type: str,
    event_id: int,
    data: dict[str, Any],
) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )

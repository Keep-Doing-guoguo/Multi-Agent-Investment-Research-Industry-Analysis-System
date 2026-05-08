from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.memory.sqlite_store import SQLiteStore


DEFAULT_RECENT_TURNS_LIMIT = 20


class MemoryManager:
    def __init__(
        self,
        store: SQLiteStore | None = None,
        recent_turns_limit: int = DEFAULT_RECENT_TURNS_LIMIT,
    ) -> None:
        self.store = store or SQLiteStore()
        self.recent_turns_limit = recent_turns_limit

    def init_db(self) -> None:
        self.store.init_db()

    def create_session(self, title: str | None = None) -> str:
        session_id = self._new_id("session")
        self.store.create_session(session_id=session_id, title=title)
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        self.get_session(session_id)
        return self.store.insert_turn(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
        )

    def get_recent_turns(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self.get_session(session_id)
        return self.store.get_recent_turns(
            session_id=session_id,
            limit=limit or self.recent_turns_limit,
        )

    def get_summary(self, session_id: str) -> str:
        self.get_session(session_id)
        return self.store.get_summary(session_id)

    def update_summary(self, session_id: str, summary: str) -> None:
        self.get_session(session_id)
        self.store.update_summary(session_id=session_id, summary=summary)

    def get_structured_memory(self, session_id: str) -> dict[str, Any]:
        self.get_session(session_id)
        return self.store.get_structured_memory(session_id)

    def patch_structured_memory(
        self,
        session_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        self.get_session(session_id)
        current = self.store.get_structured_memory(session_id)
        merged = merge_dicts(current, patch, list_strategy="append_unique")
        self.store.update_structured_memory(session_id=session_id, payload=merged)
        return merged

    def create_run(
        self,
        session_id: str,
        research_topic: str,
        request: dict[str, Any] | None = None,
    ) -> str:
        self.get_session(session_id)
        run_id = self._new_id("run")
        self.store.create_run(
            run_id=run_id,
            session_id=session_id,
            research_topic=research_topic,
            status="pending",
        )
        self.store.update_run_state(
            run_id=run_id,
            payload={
                "current_step": "created",
                "request": request or {"research_topic": research_topic},
                "triage_result": {},
                "research_result": {},
                "analysis_draft": "",
                "risk_findings": [],
                "final_report": "",
                "errors": [],
                "warnings": [],
                "decision": "",
            },
        )
        self.emit_run_event(
            run_id=run_id,
            event_type="run_created",
            payload={"research_topic": research_topic},
        )
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        return run

    def update_run_status(
        self,
        run_id: str,
        status: str,
        current_agent: str | None = None,
    ) -> None:
        self.get_run(run_id)
        self.store.update_run_status(
            run_id=run_id,
            status=status,
            current_agent=current_agent,
        )

    def increment_run_retry_count(self, run_id: str) -> int:
        self.get_run(run_id)
        return self.store.increment_run_retry_count(run_id)

    def increment_run_recollect_count(self, run_id: str) -> int:
        self.get_run(run_id)
        return self.store.increment_run_recollect_count(run_id)

    def get_run_state(self, run_id: str) -> dict[str, Any]:
        self.get_run(run_id)
        return self.store.get_run_state(run_id)

    def patch_run_state(
        self,
        run_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        self.get_run(run_id)
        current = self.store.get_run_state(run_id)
        merged = merge_dicts(current, patch, list_strategy="replace")
        self.store.update_run_state(run_id=run_id, payload=merged)
        return merged

    def emit_run_event(
        self,
        run_id: str,
        event_type: str,
        agent_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        self.get_run(run_id)
        return self.store.insert_run_event(
            run_id=run_id,
            event_type=event_type,
            agent_name=agent_name,
            payload=payload,
        )

    def get_run_events(
        self,
        run_id: str,
        after_event_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.get_run(run_id)
        return self.store.get_run_events(
            run_id=run_id,
            after_event_id=after_event_id,
            limit=limit,
        )

    def build_context_for_agent(
        self,
        session_id: str,
        run_id: str,
        agent_name: str,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        run = self.get_run(run_id)
        if run["session_id"] != session_id:
            raise ValueError(
                f"Run {run_id} does not belong to session {session_id}"
            )

        return {
            "agent_name": agent_name,
            "session": session,
            "run": run,
            "structured_memory": self.store.get_structured_memory(session_id),
            "conversation_summary": self.store.get_summary(session_id),
            "recent_turns": self.store.get_recent_turns(
                session_id=session_id,
                limit=self.recent_turns_limit,
            ),
            "run_state": self.store.get_run_state(run_id),
        }

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"


def merge_dicts(
    current: dict[str, Any],
    patch: dict[str, Any],
    list_strategy: str,
) -> dict[str, Any]:
    if list_strategy not in {"append_unique", "replace"}:
        raise ValueError(f"Unsupported list strategy: {list_strategy}")

    result = deepcopy(current)
    for key, value in patch.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = merge_dicts(existing, value, list_strategy=list_strategy)
        elif (
            list_strategy == "append_unique"
            and isinstance(existing, list)
            and isinstance(value, list)
        ):
            result[key] = append_unique(existing, value)
        else:
            result[key] = deepcopy(value)
    return result


def append_unique(existing: list[Any], incoming: list[Any]) -> list[Any]:
    result = deepcopy(existing)
    for item in incoming:
        if item not in result:
            result.append(deepcopy(item))
    return result

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateResearchRunRequest(BaseModel):
    query: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    title: str | None = None


class RunResponse(BaseModel):
    run_id: str
    session_id: str
    research_topic: str
    status: str
    current_agent: str | None = None
    retry_count: int
    recollect_count: int
    state: dict[str, Any]
    workflow: dict[str, Any] | None = None


class RunResultResponse(BaseModel):
    run_id: str
    session_id: str
    status: str
    final_report: str
    supervisor_result: dict[str, Any]
    risk_findings: list[dict[str, Any]]


class RunEventResponse(BaseModel):
    event_id: int
    run_id: str
    event_type: str
    agent_name: str | None = None
    payload: dict[str, Any]
    created_at: str

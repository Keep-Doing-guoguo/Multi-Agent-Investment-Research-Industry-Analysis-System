from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_research_service
from app.api.schemas import (
    CreateResearchRunRequest,
    CreateSessionMessageRequest,
    CreateSessionRequest,
    RunEventResponse,
    RunResponse,
    RunResultResponse,
    SessionResponse,
)
from app.services.research_service import ResearchService
from app.workflow.runner import WorkflowError


router = APIRouter(prefix="/api/research", tags=["research"])
sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@sessions_router.post("", response_model=SessionResponse)
def create_session(
    request: CreateSessionRequest,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> dict:
    return service.create_session(title=request.title)


@sessions_router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> dict:
    try:
        return service.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@sessions_router.post("/{session_id}/messages", response_model=RunResponse)
def create_session_message(
    session_id: str,
    request: CreateSessionMessageRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> dict:
    try:
        payload = service.create_run_for_session(
            session_id=session_id,
            query=request.query,
            topic=request.topic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    background_tasks.add_task(
        service.execute_run,
        session_id=session_id,
        run_id=payload["run_id"],
    )
    return payload


@router.post("/runs", response_model=RunResponse)
def create_research_run(
    request: CreateResearchRunRequest,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> dict:
    try:
        return service.create_and_run(
            session_id=request.session_id,
            query=request.query,
            topic=request.topic,
            title=request.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_research_run(
    run_id: str,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> dict:
    try:
        return service.get_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/result", response_model=RunResultResponse)
def get_research_run_result(
    run_id: str,
    service: Annotated[ResearchService, Depends(get_research_service)],
) -> dict:
    try:
        return service.get_run_result(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events", response_model=list[RunEventResponse])
def get_research_run_events(
    run_id: str,
    service: Annotated[ResearchService, Depends(get_research_service)],
    after_event_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    try:
        return service.get_run_events(
            run_id=run_id,
            after_event_id=after_event_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events/stream")
def stream_research_run_events(
    run_id: str,
    service: Annotated[ResearchService, Depends(get_research_service)],
    after_event_id: int | None = Query(default=None, ge=0),
    poll_interval_seconds: float = Query(default=1.0, gt=0, le=10),
    max_idle_polls: int = Query(default=30, ge=1, le=3600),
) -> StreamingResponse:
    try:
        stream = service.stream_run_events(
            run_id=run_id,
            after_event_id=after_event_id,
            poll_interval_seconds=poll_interval_seconds,
            max_idle_polls=max_idle_polls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

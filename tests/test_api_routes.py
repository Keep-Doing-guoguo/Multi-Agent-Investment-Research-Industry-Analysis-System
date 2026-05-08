from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from app.api.deps import get_research_service
from app.main import create_app


class FakeResearchService:
    def __init__(self) -> None:
        self.run_payload = {
            "run_id": "run_1",
            "session_id": "session_1",
            "research_topic": "中国新能源汽车行业",
            "status": "completed",
            "current_agent": "SupervisorAgent",
            "retry_count": 0,
            "recollect_count": 0,
            "state": {
                "final_report": "final report",
                "risk_findings": [],
            },
            "workflow": {
                "session_id": "session_1",
                "run_id": "run_1",
                "status": "completed",
                "final_report": "final report",
                "steps_executed": 5,
            },
        }

    def create_and_run(self, *, query: str, topic: str, title: str | None = None) -> dict[str, Any]:
        self.query = query
        self.topic = topic
        self.title = title
        return self.run_payload

    def get_run(self, run_id: str) -> dict[str, Any]:
        if run_id != "run_1":
            raise ValueError("Run not found")
        return self.run_payload

    def get_run_result(self, run_id: str) -> dict[str, Any]:
        if run_id != "run_1":
            raise ValueError("Run not found")
        return {
            "run_id": "run_1",
            "session_id": "session_1",
            "status": "completed",
            "final_report": "final report",
            "supervisor_result": {"summary": "done"},
            "risk_findings": [],
        }

    def get_run_events(
        self,
        *,
        run_id: str,
        after_event_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if run_id != "run_1":
            raise ValueError("Run not found")
        return [
            {
                "event_id": 1,
                "run_id": "run_1",
                "event_type": "run_created",
                "agent_name": None,
                "payload": {"research_topic": "中国新能源汽车行业"},
                "created_at": "2026-05-07T00:00:00+00:00",
            }
        ]

    def stream_run_events(
        self,
        *,
        run_id: str,
        after_event_id: int | None = None,
        poll_interval_seconds: float = 1.0,
        max_idle_polls: int = 30,
    ):
        if run_id != "run_1":
            raise ValueError("Run not found")
        yield (
            "id: 1\n"
            "event: run_created\n"
            'data: {"event_id": 1, "run_id": "run_1", "event_type": "run_created"}\n\n'
        )


class ApiRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.fake_service = FakeResearchService()
        self.app.dependency_overrides[get_research_service] = lambda: self.fake_service
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_create_research_run(self) -> None:
        response = self.client.post(
            "/api/research/runs",
            json={
                "query": "帮我分析中国新能源汽车行业",
                "topic": "中国新能源汽车行业",
                "title": "Demo",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["run_id"], "run_1")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(self.fake_service.query, "帮我分析中国新能源汽车行业")

    def test_get_research_run(self) -> None:
        response = self.client.get("/api/research/runs/run_1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["final_report"], "final report")

    def test_get_research_run_result(self) -> None:
        response = self.client.get("/api/research/runs/run_1/result")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["final_report"], "final report")

    def test_get_research_run_events(self) -> None:
        response = self.client.get("/api/research/runs/run_1/events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["event_type"], "run_created")

    def test_stream_research_run_events(self) -> None:
        with self.client.stream(
            "GET",
            "/api/research/runs/run_1/events/stream",
        ) as response:
            body = response.read().decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("event: run_created", body)
        self.assertIn("data:", body)

    def test_get_unknown_run_returns_404(self) -> None:
        response = self.client.get("/api/research/runs/missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

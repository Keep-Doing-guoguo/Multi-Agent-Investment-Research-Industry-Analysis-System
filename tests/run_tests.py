from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.agents.analysis_agent import AnalysisAgent
from app.agents.research_agent import ResearchAgent
from app.agents.risk_agent import RiskAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.agents.triage_agent import TriageAgent
from app.api.deps import get_research_service
from app.llm.settings import load_llm_settings
from app.main import create_app
from app.memory.manager import MemoryManager
from app.memory.sqlite_store import SQLiteStore
from app.models.agent_outputs import (
    AnalysisFinding,
    AnalysisOutput,
    ResearchDirection,
    ResearchOutput,
    ResearchType,
    RiskDecision,
    RiskFinding,
    RiskOutput,
    Severity,
    SourceItem,
    SupervisorOutput,
    TriageOutput,
)
from app.services.research_service import ResearchService, format_sse_event
import app.tools.china_research_tools as china_tools
from app.tools.china_research_tools import announcement_search, build_china_tool_registry
from app.tools.mock_research_tools import build_default_tool_registry
from app.tools.registry import SearchToolArgs, ToolArgumentError, ToolNotFoundError
from app.workflow.runner import (
    LoopLimitExceededError,
    ResearchWorkflowRunner,
    WorkflowConfig,
    WorkflowResult,
)


T = TypeVar("T", bound=BaseModel)


def make_memory() -> tuple[tempfile.TemporaryDirectory, MemoryManager]:
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test.sqlite3"
    memory = MemoryManager(SQLiteStore(db_path=db_path), recent_turns_limit=2)
    memory.init_db()
    return temp_dir, memory


def assert_raises(exc_type: type[BaseException], fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    raise AssertionError(f"Expected {exc_type.__name__}")


@contextmanager
def temporary_attr(obj: Any, attr_name: str, value: Any):
    original = getattr(obj, attr_name)
    setattr(obj, attr_name, value)
    try:
        yield
    finally:
        setattr(obj, attr_name, original)


@contextmanager
def temporary_environ(values: dict[str, str]):
    original = os.environ.copy()
    os.environ.clear()
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def test_sqlite_store_round_trip() -> None:
    temp_dir, memory = make_memory()
    try:
        session_id = memory.create_session("Demo")
        memory.append_turn(session_id, "user", "query 1")
        memory.append_turn(session_id, "assistant", "response 1")
        memory.patch_structured_memory(session_id, {"risk_focus": ["价格战"]})
        run_id = memory.create_run(session_id, "新能源汽车行业")
        memory.patch_run_state(run_id, {"current_step": "triage"})
        memory.emit_run_event(run_id, "agent_started", "TriageAgent", {"message": "start"})

        assert memory.get_session(session_id)["title"] == "Demo"
        assert [turn["content"] for turn in memory.get_recent_turns(session_id)] == [
            "query 1",
            "response 1",
        ]
        assert memory.get_structured_memory(session_id) == {"risk_focus": ["价格战"]}
        assert memory.get_run_state(run_id)["current_step"] == "triage"
        assert [event["event_type"] for event in memory.get_run_events(run_id)] == [
            "run_created",
            "agent_started",
        ]
    finally:
        temp_dir.cleanup()


def test_memory_manager_build_context() -> None:
    temp_dir, memory = make_memory()
    try:
        session_id = memory.create_session("Demo")
        memory.append_turn(session_id, "user", "query 1")
        memory.append_turn(session_id, "assistant", "response 1")
        memory.append_turn(session_id, "user", "query 2")
        memory.update_summary(session_id, "用户正在研究新能源汽车行业。")
        memory.patch_structured_memory(session_id, {"risk_focus": ["价格战"]})
        run_id = memory.create_run(session_id, "新能源汽车行业", {"query": "query 2"})

        context = memory.build_context_for_agent(session_id, run_id, "TriageAgent")

        assert context["conversation_summary"] == "用户正在研究新能源汽车行业。"
        assert context["structured_memory"] == {"risk_focus": ["价格战"]}
        assert [turn["content"] for turn in context["recent_turns"]] == ["response 1", "query 2"]
        assert context["run_state"]["request"] == {"query": "query 2"}
    finally:
        temp_dir.cleanup()


def test_agent_output_validation() -> None:
    output = TriageOutput(
        agent_name="TriageAgent",
        summary="识别为行业分析",
        research_type=ResearchType.INDUSTRY_ANALYSIS,
        target="新能源汽车行业",
        directions=[ResearchDirection(name="竞争格局", reason="行业分析需要")],
    )
    assert output.to_dict()["research_type"] == "industry_analysis"
    assert_raises(
        ValidationError,
        RiskOutput,
        agent_name="RiskAgent",
        summary="bad",
        decision="continue",
    )
    assert_raises(
        ValidationError,
        RiskFinding,
        finding_type="evidence_gap",
        severity=Severity.HIGH,
        message="缺少数据",
        suggested_action="补充数据",
        extra_field=True,
    )


def test_mock_tool_registry() -> None:
    registry = build_default_tool_registry()
    assert {tool["name"] for tool in registry.list_tools()} == {
        "news_search",
        "announcement_search",
        "financial_report_search",
        "industry_data_search",
    }
    result = registry.execute("industry_data_search", {"query": "新能源汽车行业", "limit": 1})
    assert result.tool_name == "industry_data_search"
    assert len(result.items) == 1
    assert_raises(ToolNotFoundError, registry.execute, "unknown_tool", {"query": "test"})
    assert_raises(ToolArgumentError, registry.execute, "news_search", {"query": "", "limit": 1})


def test_china_tool_registry_and_cninfo_parse() -> None:
    registry = build_china_tool_registry()
    assert {tool["name"] for tool in registry.list_tools()} == {
        "news_search",
        "announcement_search",
        "financial_report_search",
        "industry_data_search",
    }
    def fake_post_form(*args, **kwargs):
        return {
            "announcements": [
                {
                    "announcementTitle": "2025年年度报告",
                    "adjunctUrl": "finalpage/2026-04-01/test.PDF",
                    "announcementTime": 1775001600000,
                    "secName": "测试公司",
                    "secCode": "000001",
                    "orgId": "gssz0000001",
                    "announcementId": "abc",
                }
            ]
        }

    with temporary_attr(china_tools, "_post_form", fake_post_form):
        result = announcement_search(SearchToolArgs(query="测试公司", limit=1))
    assert result.items[0].metadata["source"] == "巨潮资讯网"
    assert "static.cninfo.com.cn" in result.items[0].url


def test_llm_settings_qwen_and_openai() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        env_path = Path(temp_dir) / ".env"
        env_path.write_text("QWEN_API_KEY=test-key\n", encoding="utf-8")
        with temporary_environ({}):
            settings = load_llm_settings(env_path)
    assert settings.provider == "qwen"
    assert settings.model == "qwen-plus"

    with tempfile.TemporaryDirectory() as temp_dir:
        env_path = Path(temp_dir) / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "LLM_PROVIDER=openai",
                    "OPENAI_API_KEY=openai-key",
                    "OPENAI_MODEL=gpt-test",
                    "OPENAI_BASE_URL=https://example.test/v1",
                ]
            ),
            encoding="utf-8",
        )
        with temporary_environ({}):
            settings = load_llm_settings(env_path)
    assert settings.provider == "openai"
    assert settings.base_url == "https://example.test/v1"


class FakeTriageLLM:
    def generate_structured(self, *, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        output = TriageOutput(
            agent_name="TriageAgent",
            summary="识别为行业分析任务",
            research_type=ResearchType.INDUSTRY_ANALYSIS,
            target="中国新能源汽车行业",
            directions=[ResearchDirection(name="竞争格局", reason="行业分析需要")],
            constraints=["结论谨慎"],
            required_tools=["news_search", "industry_data_search"],
        )
        return output_model.model_validate(output.to_dict())


class FakeResearchLLM:
    def generate_structured(self, *, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        output = ResearchOutput(
            agent_name="ResearchAgent",
            summary="已收集资料",
            sources=[SourceItem(title="行业数据", source_type="industry_data", summary="需求增长")],
            key_materials=["行业需求仍有增长空间"],
            data_gaps=["缺少盈利能力对比"],
        )
        return output_model.model_validate(output.to_dict())


class FakeAnalysisLLM:
    def generate_structured(self, *, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        output = AnalysisOutput(
            agent_name="AnalysisAgent",
            summary="行业有增长但竞争较强",
            findings=[
                AnalysisFinding(
                    claim="行业需求仍有增长空间",
                    evidence=["行业数据"],
                    confidence="medium",
                )
            ],
            growth_drivers=["出口增长"],
            risk_points=["价格战"],
            draft_report="分析草稿",
        )
        return output_model.model_validate(output.to_dict())


class FakeRiskLLM:
    def __init__(self, decision: RiskDecision = RiskDecision.PASS) -> None:
        self.decision = decision

    def generate_structured(self, *, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        output = RiskOutput(
            agent_name="RiskAgent",
            summary="风险审查完成",
            decision=self.decision,
            findings=[
                RiskFinding(
                    finding_type="missing_risk",
                    severity=Severity.MEDIUM,
                    message="需要提示价格战",
                    suggested_action="保留风险提示",
                )
            ],
            reason="证据基本充分",
        )
        return output_model.model_validate(output.to_dict())


class FakeSupervisorLLM:
    def generate_structured(self, *, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        output = SupervisorOutput(
            agent_name="SupervisorAgent",
            summary="最终报告完成",
            final_report="最终报告",
            key_conclusions=["行业需求仍有增长空间"],
            risk_summary=["价格战风险"],
            follow_up_suggestions=["跟踪月度销量"],
        )
        return output_model.model_validate(output.to_dict())


def test_agents_linear_outputs() -> None:
    temp_dir, memory = make_memory()
    try:
        session_id = memory.create_session("Demo")
        run_id = memory.create_run(session_id, "中国新能源汽车行业", {"query": "分析"})
        tools = build_default_tool_registry()

        triage = TriageAgent(memory, FakeTriageLLM(), tools).run(session_id, run_id)
        research = ResearchAgent(memory, FakeResearchLLM(), tools).run(session_id, run_id)
        analysis = AnalysisAgent(memory, FakeAnalysisLLM()).run(session_id, run_id)
        risk = RiskAgent(memory, FakeRiskLLM()).run(session_id, run_id)
        supervisor = SupervisorAgent(memory, FakeSupervisorLLM()).run(session_id, run_id)

        state = memory.get_run_state(run_id)
        assert triage.target == "中国新能源汽车行业"
        assert research.key_materials == ["行业需求仍有增长空间"]
        assert analysis.draft_report == "分析草稿"
        assert risk.decision == "pass"
        assert supervisor.final_report == "最终报告"
        assert state["final_report"] == "最终报告"
        assert memory.get_run(run_id)["status"] == "completed"
    finally:
        temp_dir.cleanup()


class SimpleTriageAgent:
    def run(self, session_id: str, run_id: str) -> TriageOutput:
        output = TriageOutput(
            agent_name="TriageAgent",
            summary="triage",
            research_type="industry_analysis",
            target="中国新能源汽车行业",
        )
        TEST_MEMORY.patch_run_state(run_id, {"triage_result": output.to_dict()})
        return output


class SimpleResearchAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, session_id: str, run_id: str) -> ResearchOutput:
        self.calls += 1
        output = ResearchOutput(agent_name="ResearchAgent", summary="research")
        TEST_MEMORY.patch_run_state(run_id, {"research_result": output.to_dict()})
        return output


class SimpleAnalysisAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, session_id: str, run_id: str) -> AnalysisOutput:
        self.calls += 1
        output = AnalysisOutput(agent_name="AnalysisAgent", summary="analysis", draft_report="draft")
        TEST_MEMORY.patch_run_state(run_id, {"analysis_result": output.to_dict(), "analysis_draft": "draft"})
        return output


class SimpleRiskAgent:
    def __init__(self, decisions: list[RiskDecision]) -> None:
        self.decisions = decisions
        self.index = 0

    def run(self, session_id: str, run_id: str) -> RiskOutput:
        decision = self.decisions[min(self.index, len(self.decisions) - 1)]
        self.index += 1
        output = RiskOutput(agent_name="RiskAgent", summary="risk", decision=decision)
        TEST_MEMORY.patch_run_state(run_id, {"risk_decision": output.decision, "decision": output.decision})
        return output


class SimpleSupervisorAgent:
    def run(self, session_id: str, run_id: str) -> SupervisorOutput:
        output = SupervisorOutput(agent_name="SupervisorAgent", summary="final", final_report="final report")
        TEST_MEMORY.patch_run_state(run_id, {"final_report": output.final_report})
        TEST_MEMORY.update_run_status(run_id, "completed", "SupervisorAgent")
        TEST_MEMORY.emit_run_event(run_id, "run_completed", "SupervisorAgent", {})
        return output


TEST_MEMORY: MemoryManager


def build_simple_runner(decisions: list[RiskDecision], config: WorkflowConfig | None = None):
    research = SimpleResearchAgent()
    analysis = SimpleAnalysisAgent()
    runner = ResearchWorkflowRunner(
        memory=TEST_MEMORY,
        triage_agent=SimpleTriageAgent(),
        research_agent=research,
        analysis_agent=analysis,
        risk_agent=SimpleRiskAgent(decisions),
        supervisor_agent=SimpleSupervisorAgent(),
        config=config,
    )
    return runner, research, analysis


def test_workflow_runner_pass_retry_recollect_and_failure() -> None:
    global TEST_MEMORY
    temp_dir, TEST_MEMORY = make_memory()
    try:
        session_id = TEST_MEMORY.create_session("Demo")
        run_id = TEST_MEMORY.create_run(session_id, "新能源汽车行业")
        runner, _, _ = build_simple_runner([RiskDecision.PASS])
        result = runner.run(session_id, run_id)
        assert result.status == "completed"
        assert result.final_report == "final report"

        session_id = TEST_MEMORY.create_session("Demo2")
        run_id = TEST_MEMORY.create_run(session_id, "新能源汽车行业")
        runner, _, analysis = build_simple_runner([RiskDecision.RETRY, RiskDecision.PASS])
        runner.run(session_id, run_id)
        assert TEST_MEMORY.get_run(run_id)["retry_count"] == 1
        assert analysis.calls == 2

        session_id = TEST_MEMORY.create_session("Demo3")
        run_id = TEST_MEMORY.create_run(session_id, "新能源汽车行业")
        runner, research, _ = build_simple_runner([RiskDecision.RECOLLECT, RiskDecision.PASS])
        runner.run(session_id, run_id)
        assert TEST_MEMORY.get_run(run_id)["recollect_count"] == 1
        assert research.calls == 2

        session_id = TEST_MEMORY.create_session("Demo4")
        run_id = TEST_MEMORY.create_run(session_id, "新能源汽车行业")
        runner, _, _ = build_simple_runner(
            [RiskDecision.RETRY, RiskDecision.RETRY],
            WorkflowConfig(max_retry_count=1, max_total_steps=10),
        )
        assert_raises(LoopLimitExceededError, runner.run, session_id, run_id)
        assert TEST_MEMORY.get_run(run_id)["status"] == "failed"
    finally:
        temp_dir.cleanup()


class FakeWorkflowRunnerForService:
    def __init__(self, memory: MemoryManager) -> None:
        self.memory = memory

    def run(self, session_id: str, run_id: str) -> WorkflowResult:
        self.memory.patch_run_state(run_id, {"final_report": f"final report for {run_id}"})
        self.memory.update_run_status(run_id, "completed", "SupervisorAgent")
        return WorkflowResult(
            session_id=session_id,
            run_id=run_id,
            status="completed",
            final_report=f"final report for {run_id}",
            steps_executed=5,
        )


def test_research_service_reuses_session_memory_per_run() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    try:
        db_path = Path(temp_dir.name) / "test.sqlite3"
        memory = MemoryManager(SQLiteStore(db_path=db_path), recent_turns_limit=10)
        memory.init_db()
        service = ResearchService(
            memory=memory,
            workflow_runner=FakeWorkflowRunnerForService(memory),
        )

        session = service.create_session("新能源汽车行业")
        first_run = service.create_and_run(
            session_id=session["session_id"],
            query="分析价格战",
            topic="新能源汽车行业",
        )
        second_run = service.create_run_for_session(
            session_id=session["session_id"],
            query="继续分析出口风险",
            topic="新能源汽车行业",
        )

        turns = memory.get_recent_turns(session["session_id"], limit=10)
        assert [turn["role"] for turn in turns] == ["user", "assistant", "user"]
        assert turns[0]["content"] == "分析价格战"
        assert turns[1]["metadata"]["run_id"] == first_run["run_id"]
        assert turns[2]["content"] == "继续分析出口风险"
        assert second_run["session_id"] == session["session_id"]
        assert first_run["run_id"] != second_run["run_id"]
    finally:
        temp_dir.cleanup()


class FakeResearchService:
    def create_and_run(
        self,
        *,
        query: str,
        topic: str,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "run_id": "run_1",
            "session_id": session_id or "session_1",
            "research_topic": topic,
            "status": "completed",
            "current_agent": "SupervisorAgent",
            "retry_count": 0,
            "recollect_count": 0,
            "state": {"final_report": "final report"},
            "workflow": {"run_id": "run_1", "session_id": "session_1", "status": "completed", "final_report": "final report", "steps_executed": 5},
        }

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        return {
            "session_id": "session_1",
            "title": title,
            "status": "active",
            "created_at": "2026-05-08T00:00:00+00:00",
            "updated_at": "2026-05-08T00:00:00+00:00",
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        if session_id != "session_1":
            raise ValueError("Session not found")
        return self.create_session("Demo")

    def create_run_for_session(
        self,
        *,
        session_id: str,
        query: str,
        topic: str | None = None,
    ) -> dict[str, Any]:
        if session_id != "session_1":
            raise ValueError("Session not found")
        return {
            "run_id": "run_1",
            "session_id": session_id,
            "research_topic": topic or query,
            "status": "pending",
            "current_agent": None,
            "retry_count": 0,
            "recollect_count": 0,
            "state": {"request": {"query": query}},
            "workflow": None,
        }

    def execute_run(self, *, session_id: str, run_id: str):
        if session_id != "session_1" or run_id != "run_1":
            raise ValueError("Run not found")
        return None

    def get_run(self, run_id: str) -> dict[str, Any]:
        if run_id != "run_1":
            raise ValueError("Run not found")
        return self.create_and_run(query="q", topic="中国新能源汽车行业")

    def get_run_result(self, run_id: str) -> dict[str, Any]:
        if run_id != "run_1":
            raise ValueError("Run not found")
        return {
            "run_id": "run_1",
            "session_id": "session_1",
            "status": "completed",
            "final_report": "final report",
            "supervisor_result": {},
            "risk_findings": [],
        }

    def get_run_events(self, *, run_id: str, after_event_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if run_id != "run_1":
            raise ValueError("Run not found")
        return [{"event_id": 1, "run_id": "run_1", "event_type": "run_created", "agent_name": None, "payload": {}, "created_at": "2026-05-08T00:00:00+00:00"}]

    def stream_run_events(self, *, run_id: str, after_event_id: int | None = None, poll_interval_seconds: float = 1.0, max_idle_polls: int = 30):
        if run_id != "run_1":
            raise ValueError("Run not found")
        yield 'id: 1\nevent: run_created\ndata: {"event_id": 1}\n\n'


def test_api_routes_and_sse_format() -> None:
    app = create_app()
    app.dependency_overrides[get_research_service] = lambda: FakeResearchService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/research/runs",
            json={"query": "分析", "topic": "中国新能源汽车行业", "title": "Demo"},
        )
        assert response.status_code == 200
        assert response.json()["run_id"] == "run_1"
        response = client.post("/api/sessions", json={"title": "Demo"})
        assert response.status_code == 200
        assert response.json()["session_id"] == "session_1"
        response = client.post(
            "/api/sessions/session_1/messages",
            json={"query": "继续分析出口风险", "topic": "中国新能源汽车行业"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        assert client.get("/api/research/runs/run_1").status_code == 200
        assert client.get("/api/research/runs/run_1/result").json()["final_report"] == "final report"
        assert client.get("/api/research/runs/run_1/events").json()[0]["event_type"] == "run_created"
        with client.stream("GET", "/api/research/runs/run_1/events/stream") as stream_response:
            body = stream_response.read().decode("utf-8")
        assert "event: run_created" in body
    finally:
        app.dependency_overrides.clear()

    frame = format_sse_event(event_type="run_created", event_id=1, data={"event_id": 1})
    data_line = [line.removeprefix("data: ") for line in frame.splitlines() if line.startswith("data: ")][0]
    assert json.loads(data_line) == {"event_id": 1}


TESTS = [
    test_sqlite_store_round_trip,
    test_memory_manager_build_context,
    test_agent_output_validation,
    test_mock_tool_registry,
    test_china_tool_registry_and_cninfo_parse,
    test_llm_settings_qwen_and_openai,
    test_agents_linear_outputs,
    test_workflow_runner_pass_retry_recollect_and_failure,
    test_research_service_reuses_session_memory_per_run,
    test_api_routes_and_sse_format,
]


def main() -> None:
    passed = 0
    for test in TESTS:
        test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"\n{passed} function tests passed.")


if __name__ == "__main__":
    main()

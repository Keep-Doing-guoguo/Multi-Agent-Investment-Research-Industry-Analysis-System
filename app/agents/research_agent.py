from __future__ import annotations

import json
from typing import Any

from app.llm.client import LLMClient
from app.memory.manager import MemoryManager
from app.models.agent_outputs import ResearchOutput
from app.tools.registry import ToolExecutionError, ToolRegistry

'''
1. 读取 run_state.triage_result
2. 根据 required_tools 调用 mock tools
3. 写入 tool_started / tool_completed / tool_failed events
4. 把 tool_results 交给 LLM
5. 生成 ResearchOutput
6. 写入 run_state.tool_results
7. 写入 run_state.research_result
8. 写入 agent_completed event

'''
RESEARCH_SYSTEM_PROMPT = """
You are ResearchAgent in a multi-agent investment research system.
Your job is to turn tool results into structured research materials.
Do not make final investment conclusions. Focus on evidence, useful materials, and data gaps.
Return only valid JSON matching the requested schema. Do not include markdown.
""".strip()


DEFAULT_RESEARCH_TOOLS = [
    "news_search",
    "announcement_search",
    "financial_report_search",
    "industry_data_search",
]


class ResearchAgent:
    name = "ResearchAgent"

    def __init__(
        self,
        memory: MemoryManager,
        llm: LLMClient,
        tools: ToolRegistry,
    ) -> None:
        self.memory = memory
        self.llm = llm
        self.tools = tools

    def run(self, session_id: str, run_id: str) -> ResearchOutput:
        self.memory.update_run_status(run_id, status="running", current_agent=self.name)
        self.memory.emit_run_event(
            run_id,
            event_type="agent_started",
            agent_name=self.name,
            payload={"message": "开始收集研究资料"},
        )

        context = self.memory.build_context_for_agent(
            session_id=session_id,
            run_id=run_id,
            agent_name=self.name,
        )
        tool_results = self._execute_required_tools(run_id, context)
        context["tool_results"] = tool_results

        output = self.llm.generate_structured(
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(context),
            output_model=ResearchOutput,
        )

        output_dict = output.to_dict()
        self.memory.patch_run_state(
            run_id,
            {
                "current_step": "research_completed",
                "tool_results": tool_results,
                "research_result": output_dict,
            },
        )
        self.memory.emit_run_event(
            run_id,
            event_type="agent_completed",
            agent_name=self.name,
            payload=output_dict,
        )
        return output

    def _execute_required_tools(
        self,
        run_id: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        triage_result = context["run_state"].get("triage_result", {})
        required_tools = triage_result.get("required_tools") or DEFAULT_RESEARCH_TOOLS
        query = self._build_tool_query(context)

        results: list[dict[str, Any]] = []
        for tool_name in required_tools:
            self.memory.emit_run_event(
                run_id,
                event_type="tool_started",
                agent_name=self.name,
                payload={"tool_name": tool_name, "query": query},
            )
            try:
                result = self.tools.execute(tool_name, {"query": query, "limit": 5})
                result_dict = result.to_dict()
                results.append(result_dict)
                self.memory.emit_run_event(
                    run_id,
                    event_type="tool_completed",
                    agent_name=self.name,
                    payload=result_dict,
                )
            except ToolExecutionError as exc:
                warning = {
                    "tool_name": tool_name,
                    "error": str(exc),
                }
                results.append(
                    {
                        "tool_name": tool_name,
                        "query": query,
                        "items": [],
                        "warnings": [str(exc)],
                        "metadata": {"failed": True},
                    }
                )
                self.memory.emit_run_event(
                    run_id,
                    event_type="tool_failed",
                    agent_name=self.name,
                    payload=warning,
                )
        return results

    def _build_tool_query(self, context: dict[str, Any]) -> str:
        triage_result = context["run_state"].get("triage_result", {})
        target = triage_result.get("target") or context["run"]["research_topic"]
        directions = [
            direction.get("name", "")
            for direction in triage_result.get("directions", [])
            if isinstance(direction, dict)
        ]
        constraints = triage_result.get("constraints", [])
        query_parts = [target, *directions, *constraints]
        return " ".join(part for part in query_parts if part).strip()

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        prompt_payload = {
            "session": context["session"],
            "run": context["run"],
            "structured_memory": context["structured_memory"],
            "conversation_summary": context["conversation_summary"],
            "recent_turns": context["recent_turns"],
            "run_state": context["run_state"],
            "tool_results": context["tool_results"],
            "required_output_schema": {
                "agent_name": self.name,
                "summary": "short summary of collected materials",
                "sources": [
                    {
                        "title": "source title",
                        "source_type": "news | announcement | financial_report | industry_data",
                        "url": None,
                        "published_at": "YYYY-MM-DD or null",
                        "summary": "source summary",
                        "metadata": {},
                    }
                ],
                "key_materials": ["important materials or evidence"],
                "data_gaps": ["missing data or evidence gaps"],
            },
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

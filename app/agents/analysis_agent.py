from __future__ import annotations

import json
from typing import Any

from app.llm.client import LLMClient
from app.memory.manager import MemoryManager
from app.models.agent_outputs import AnalysisOutput
'''
1. 读取 triage_result
2. 读取 research_result
3. 读取 tool_results
4. 调用 LLM 生成 AnalysisOutput
5. 写入 run_state.analysis_result
6. 写入 run_state.analysis_draft
7. 写入 agent_started / agent_completed events

'''

ANALYSIS_SYSTEM_PROMPT = """
You are AnalysisAgent in a multi-agent investment research system.
Your job is to analyze the collected research materials and produce a structured analysis draft.
Separate claims from evidence. Do not ignore data gaps. Do not perform final risk approval.
Return only valid JSON matching the requested schema. Do not include markdown.
""".strip()


class AnalysisAgent:
    name = "AnalysisAgent"

    def __init__(
        self,
        memory: MemoryManager,
        llm: LLMClient,
    ) -> None:
        self.memory = memory
        self.llm = llm

    def run(self, session_id: str, run_id: str) -> AnalysisOutput:
        self.memory.update_run_status(run_id, status="running", current_agent=self.name)
        self.memory.emit_run_event(
            run_id,
            event_type="agent_started",
            agent_name=self.name,
            payload={"message": "开始整理资料并生成分析草稿"},
        )

        context = self.memory.build_context_for_agent(
            session_id=session_id,
            run_id=run_id,
            agent_name=self.name,
        )
        output = self.llm.generate_structured(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(context),
            output_model=AnalysisOutput,
        )

        output_dict = output.to_dict()
        self.memory.patch_run_state(
            run_id,
            {
                "current_step": "analysis_completed",
                "analysis_result": output_dict,
                "analysis_draft": output.draft_report,
            },
        )
        self.memory.emit_run_event(
            run_id,
            event_type="agent_completed",
            agent_name=self.name,
            payload=output_dict,
        )
        return output

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        prompt_payload = {
            "session": context["session"],
            "run": context["run"],
            "structured_memory": context["structured_memory"],
            "conversation_summary": context["conversation_summary"],
            "recent_turns": context["recent_turns"],
            "triage_result": context["run_state"].get("triage_result", {}),
            "research_result": context["run_state"].get("research_result", {}),
            "tool_results": context["run_state"].get("tool_results", []),
            "required_output_schema": {
                "agent_name": self.name,
                "summary": "short summary of analysis",
                "findings": [
                    {
                        "claim": "analytical claim",
                        "evidence": ["evidence refs or source summaries"],
                        "confidence": "low | medium | high",
                    }
                ],
                "growth_drivers": ["growth drivers"],
                "risk_points": ["risk points"],
                "draft_report": "structured analysis draft, not final report",
            },
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

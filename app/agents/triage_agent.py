from __future__ import annotations

import json
from typing import Any

from app.llm.client import LLMClient
from app.memory.manager import MemoryManager
from app.models.agent_outputs import TriageOutput
from app.tools.registry import ToolRegistry

'''
1. 读取 session memory 和 recent turns
2. 判断研究类型
3. 提取研究对象 target
4. 规划研究方向 directions
5. 判断需要哪些 tools
6. 输出 TriageOutput
7. 写入 run_state.triage_result
8. patch structured_memory
9. emit agent_started / agent_completed

'''
TRIAGE_SYSTEM_PROMPT = """
You are TriageAgent in a multi-agent investment research system.
Your job is to classify the research request, identify the target, and plan what information later agents need.
Return only valid JSON matching the requested schema. Do not include markdown.

Allowed research_type values:
- company_analysis
- industry_analysis
- policy_impact
- financial_report_review
- risk_event_tracking
- general_research

required_tools must only use tool names provided in available_tools.
""".strip()


class TriageAgent:
    name = "TriageAgent"

    def __init__(
        self,
        memory: MemoryManager,
        llm: LLMClient,
        tools: ToolRegistry,
    ) -> None:
        self.memory = memory
        self.llm = llm
        self.tools = tools

    def run(self, session_id: str, run_id: str) -> TriageOutput:
        self.memory.update_run_status(run_id, status="running", current_agent=self.name)
        self.memory.emit_run_event(
            run_id,
            event_type="agent_started",
            agent_name=self.name,
            payload={"message": "开始识别研究任务类型和信息需求"},
        )

        context = self.memory.build_context_for_agent(
            session_id=session_id,
            run_id=run_id,
            agent_name=self.name,
        )
        output = self.llm.generate_structured(
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(context),
            output_model=TriageOutput,
        )

        output_dict = output.to_dict()
        self.memory.patch_run_state(
            run_id,
            {
                "current_step": "triage_completed",
                "triage_result": output_dict,
            },
        )
        self.memory.patch_structured_memory(
            session_id,
            {
                "research_topic": output.target,
                "research_type": output.research_type,
                "research_constraints": output.constraints,
                "research_directions": [
                    direction.model_dump(mode="json") for direction in output.directions
                ],
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
            "available_tools": self.tools.list_tools(),
            "session": context["session"],
            "run": context["run"],
            "structured_memory": context["structured_memory"],
            "conversation_summary": context["conversation_summary"],
            "recent_turns": context["recent_turns"],
            "run_state": context["run_state"],
            "required_output_schema": {
                "agent_name": self.name,
                "summary": "short summary of the triage result",
                "research_type": "one allowed research_type value",
                "target": "company, industry, policy, event, or research topic",
                "directions": [
                    {"name": "research direction", "reason": "why this matters"}
                ],
                "constraints": ["user constraints or confirmed scope"],
                "required_tools": ["tool names from available_tools"],
            },
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

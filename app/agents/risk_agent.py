from __future__ import annotations

import json
from typing import Any

from app.llm.client import LLMClient
from app.memory.manager import MemoryManager
from app.models.agent_outputs import RiskOutput

'''
1. 读取 research_result
2. 读取 tool_results
3. 读取 analysis_result
4. 读取 analysis_draft
5. 调用 LLM 生成 RiskOutput
6. 写入 run_state.risk_result
7. 写入 run_state.risk_findings
8. 写入 run_state.risk_decision
9. 写入 risk_decision event

'''
RISK_SYSTEM_PROMPT = """
You are RiskAgent in a multi-agent investment research system.
Your job is to review whether the analysis is supported by evidence and whether major risks are missing.
Choose exactly one decision:
- pass: evidence is sufficient and the draft can move to SupervisorAgent
- retry: analysis logic is weak, overstated, or internally inconsistent; return to AnalysisAgent
- recollect: evidence or source material is insufficient; return to ResearchAgent

Return only valid JSON matching the requested schema. Do not include markdown.
""".strip()


class RiskAgent:
    name = "RiskAgent"

    def __init__(
        self,
        memory: MemoryManager,
        llm: LLMClient,
    ) -> None:
        self.memory = memory
        self.llm = llm

    def run(self, session_id: str, run_id: str) -> RiskOutput:
        self.memory.update_run_status(run_id, status="running", current_agent=self.name)
        self.memory.emit_run_event(
            run_id,
            event_type="agent_started",
            agent_name=self.name,
            payload={"message": "开始审查证据、风险和过度推断"},
        )

        context = self.memory.build_context_for_agent(
            session_id=session_id,
            run_id=run_id,
            agent_name=self.name,
        )
        output = self.llm.generate_structured(
            system_prompt=RISK_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(context),
            output_model=RiskOutput,
        )

        output_dict = output.to_dict()
        self.memory.patch_run_state(
            run_id,
            {
                "current_step": "risk_completed",
                "risk_result": output_dict,
                "risk_findings": output_dict["findings"],
                "risk_decision": output_dict["decision"],
                "decision": output_dict["decision"],
            },
        )
        self.memory.emit_run_event(
            run_id,
            event_type="risk_decision",
            agent_name=self.name,
            payload={
                "decision": output_dict["decision"],
                "reason": output_dict.get("reason", ""),
                "findings": output_dict["findings"],
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
            "analysis_result": context["run_state"].get("analysis_result", {}),
            "analysis_draft": context["run_state"].get("analysis_draft", ""),
            "required_output_schema": {
                "agent_name": self.name,
                "summary": "short summary of risk review",
                "decision": "pass | retry | recollect",
                "findings": [
                    {
                        "finding_type": "evidence_gap | missing_risk | overstatement | logic_issue",
                        "severity": "low | medium | high",
                        "message": "risk finding message",
                        "suggested_action": "what should happen next",
                        "evidence_refs": ["related evidence or claim refs"],
                    }
                ],
                "reason": "why this decision was selected",
            },
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

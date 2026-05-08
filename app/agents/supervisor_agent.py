from __future__ import annotations

import json
from typing import Any

from app.llm.client import LLMClient
from app.memory.manager import MemoryManager
from app.models.agent_outputs import SupervisorOutput


SUPERVISOR_SYSTEM_PROMPT = """
You are SupervisorAgent in a multi-agent investment research system.
Your job is to synthesize triage, research, analysis, and risk review outputs into the final research report.
Keep conclusions evidence-aware and preserve risk caveats. Do not invent sources.
Return only valid JSON matching the requested schema. Do not include markdown.
""".strip()


class SupervisorAgent:
    name = "SupervisorAgent"

    def __init__(
        self,
        memory: MemoryManager,
        llm: LLMClient,
    ) -> None:
        self.memory = memory
        self.llm = llm

    def run(self, session_id: str, run_id: str) -> SupervisorOutput:
        self.memory.update_run_status(run_id, status="running", current_agent=self.name)
        self.memory.emit_run_event(
            run_id,
            event_type="agent_started",
            agent_name=self.name,
            payload={"message": "开始汇总最终研究报告"},
        )

        context = self.memory.build_context_for_agent(
            session_id=session_id,
            run_id=run_id,
            agent_name=self.name,
        )
        output = self.llm.generate_structured(
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(context),
            output_model=SupervisorOutput,
        )

        output_dict = output.to_dict()
        self.memory.patch_run_state(
            run_id,
            {
                "current_step": "supervisor_completed",
                "supervisor_result": output_dict,
                "final_report": output.final_report,
            },
        )
        self.memory.patch_structured_memory(
            session_id,
            {
                "accepted_findings": output.key_conclusions,
                "follow_up_suggestions": output.follow_up_suggestions,
            },
        )
        self.memory.emit_run_event(
            run_id,
            event_type="agent_completed",
            agent_name=self.name,
            payload=output_dict,
        )
        self.memory.update_run_status(
            run_id,
            status="completed",
            current_agent=self.name,
        )
        self.memory.emit_run_event(
            run_id,
            event_type="run_completed",
            agent_name=self.name,
            payload={"final_report": output.final_report},
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
            "analysis_result": context["run_state"].get("analysis_result", {}),
            "analysis_draft": context["run_state"].get("analysis_draft", ""),
            "risk_result": context["run_state"].get("risk_result", {}),
            "risk_findings": context["run_state"].get("risk_findings", []),
            "required_output_schema": {
                "agent_name": self.name,
                "summary": "short summary of final report",
                "final_report": "final investment research or industry analysis report",
                "key_conclusions": ["key conclusions"],
                "risk_summary": ["risk caveats"],
                "follow_up_suggestions": ["suggestions for follow-up tracking"],
            },
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

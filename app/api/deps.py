from __future__ import annotations

from functools import lru_cache

from app.agents.analysis_agent import AnalysisAgent
from app.agents.research_agent import ResearchAgent
from app.agents.risk_agent import RiskAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.agents.triage_agent import TriageAgent
from app.llm.client import OpenAILLMClient
from app.memory.manager import MemoryManager
from app.services.research_service import ResearchService
from app.tools.mock_research_tools import build_default_tool_registry
from app.workflow.runner import ResearchWorkflowRunner, WorkflowConfig


@lru_cache(maxsize=1)
def get_research_service() -> ResearchService:
    memory = MemoryManager()
    memory.init_db()
    tools = build_default_tool_registry()
    llm = OpenAILLMClient()
    runner = ResearchWorkflowRunner(
        memory=memory,
        triage_agent=TriageAgent(memory=memory, llm=llm, tools=tools),
        research_agent=ResearchAgent(memory=memory, llm=llm, tools=tools),
        analysis_agent=AnalysisAgent(memory=memory, llm=llm),
        risk_agent=RiskAgent(memory=memory, llm=llm),
        supervisor_agent=SupervisorAgent(memory=memory, llm=llm),
        config=WorkflowConfig(),
    )
    return ResearchService(memory=memory, workflow_runner=runner)

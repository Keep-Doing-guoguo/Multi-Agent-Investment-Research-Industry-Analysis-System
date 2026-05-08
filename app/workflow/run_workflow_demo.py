from __future__ import annotations

import argparse

from app.agents.analysis_agent import AnalysisAgent
from app.agents.research_agent import ResearchAgent
from app.agents.risk_agent import RiskAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.agents.triage_agent import TriageAgent
from app.llm.client import OpenAILLMClient
from app.memory.manager import MemoryManager
from app.tools.mock_research_tools import build_default_tool_registry
from app.workflow.runner import ResearchWorkflowRunner, WorkflowConfig


DEFAULT_QUERY = "帮我分析中国新能源汽车行业，重点看价格战、出口和产能过剩风险，结论要谨慎。"
DEFAULT_TOPIC = "中国新能源汽车行业"


def main() -> None:
    args = parse_args()

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
        config=WorkflowConfig(
            max_retry_count=args.max_retry_count,
            max_recollect_count=args.max_recollect_count,
            max_total_steps=args.max_total_steps,
        ),
    )

    session_id = memory.create_session(args.title)
    memory.append_turn(session_id, "user", args.query)
    run_id = memory.create_run(
        session_id=session_id,
        research_topic=args.topic,
        request={"query": args.query},
    )

    result = runner.run(session_id=session_id, run_id=run_id)
    print(f"session_id={result.session_id}")
    print(f"run_id={result.run_id}")
    print(f"status={result.status}")
    print(f"steps_executed={result.steps_executed}")
    print("\nFinal Report:\n")
    print(result.final_report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full research workflow demo.")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--title", default="Workflow Demo")
    parser.add_argument("--max-retry-count", type=int, default=2)
    parser.add_argument("--max-recollect-count", type=int, default=2)
    parser.add_argument("--max-total-steps", type=int, default=10)
    return parser.parse_args()


if __name__ == "__main__":
    main()

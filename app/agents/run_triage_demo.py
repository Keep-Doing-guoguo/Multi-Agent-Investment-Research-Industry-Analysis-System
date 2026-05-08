from __future__ import annotations

from app.agents.triage_agent import TriageAgent
from app.llm.client import OpenAILLMClient
from app.memory.manager import MemoryManager
from app.tools.mock_research_tools import build_default_tool_registry


def main() -> None:
    memory = MemoryManager()
    memory.init_db()
    tools = build_default_tool_registry()
    llm = OpenAILLMClient()
    agent = TriageAgent(memory=memory, llm=llm, tools=tools)

    query = "帮我分析中国新能源汽车行业，重点看价格战、出口和产能过剩风险，结论要谨慎。"
    session_id = memory.create_session("Triage Demo")
    memory.append_turn(session_id, "user", query)
    run_id = memory.create_run(
        session_id=session_id,
        research_topic="中国新能源汽车行业",
        request={"query": query},
    )

    output = agent.run(session_id=session_id, run_id=run_id)
    print(output.model_dump_json(indent=2))
    print(f"session_id={session_id}")
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()

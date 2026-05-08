# Agents 说明

当前已实现：

```text
TriageAgent
ResearchAgent
AnalysisAgent
RiskAgent
SupervisorAgent
```

## TriageAgent

代码位置：

```text
app/agents/triage_agent.py
```

职责：

- 读取 session memory、recent turns 和 run state
- 读取可用 tools 列表
- 调用 LLM 输出 `TriageOutput`
- 更新 `run_states.triage_result`
- 更新 `structured_memories`
- 写入 `run_events`

执行后会产生事件：

```text
agent_started
agent_completed
```

后续 Graph 会根据 `triage_result.required_tools` 和 `triage_result.research_type` 进入 ResearchAgent。

## ResearchAgent

代码位置：

```text
app/agents/research_agent.py
```

职责：

- 读取 `run_states.triage_result`
- 根据 `required_tools` 调用 mock tools
- 将 tool results 交给 LLM 整理成 `ResearchOutput`
- 更新 `run_states.tool_results`
- 更新 `run_states.research_result`
- 写入 `run_events`

执行过程中会产生事件：

```text
agent_started
tool_started
tool_completed
tool_failed
agent_completed
```

当前工具仍然是 mock：

```text
news_search
announcement_search
financial_report_search
industry_data_search
```

如果 `triage_result.required_tools` 为空，ResearchAgent 会默认调用全部 research tools。

## AnalysisAgent

代码位置：

```text
app/agents/analysis_agent.py
```

职责：

- 读取 `run_states.triage_result`
- 读取 `run_states.research_result`
- 读取 `run_states.tool_results`
- 调用 LLM 输出 `AnalysisOutput`
- 更新 `run_states.analysis_result`
- 更新 `run_states.analysis_draft`
- 写入 `run_events`

执行后会产生事件：

```text
agent_started
agent_completed
```

AnalysisAgent 只生成分析草稿，不负责风险审查，也不输出最终报告。风险审查由后续 `RiskAgent` 完成。

## RiskAgent

代码位置：

```text
app/agents/risk_agent.py
```

职责：

- 读取 `run_states.research_result`
- 读取 `run_states.tool_results`
- 读取 `run_states.analysis_result`
- 读取 `run_states.analysis_draft`
- 调用 LLM 输出 `RiskOutput`
- 更新 `run_states.risk_result`
- 更新 `run_states.risk_findings`
- 更新 `run_states.risk_decision`
- 写入 `run_events`

执行后会产生事件：

```text
agent_started
risk_decision
agent_completed
```

`risk_decision` 是后续 Graph 的分支依据：

```text
pass      -> SupervisorAgent
retry     -> AnalysisAgent
recollect -> ResearchAgent
```

## SupervisorAgent

代码位置：

```text
app/agents/supervisor_agent.py
```

职责：

- 读取 `run_states.analysis_result`
- 读取 `run_states.analysis_draft`
- 读取 `run_states.risk_result`
- 读取 `run_states.risk_findings`
- 调用 LLM 输出 `SupervisorOutput`
- 更新 `run_states.supervisor_result`
- 更新 `run_states.final_report`
- 将关键结论沉淀进 `structured_memories.accepted_findings`
- 将跟踪建议沉淀进 `structured_memories.follow_up_suggestions`
- 将 run 状态更新为 `completed`
- 写入 `run_completed` 事件

执行后会产生事件：

```text
agent_started
agent_completed
run_completed
```

到达 SupervisorAgent 意味着当前 run 已完成。

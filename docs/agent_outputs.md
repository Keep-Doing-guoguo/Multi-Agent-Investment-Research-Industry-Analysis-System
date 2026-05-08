# Agent 输出模型说明

本文档说明 `app/models/agent_outputs.py` 中定义的结构化输出模型。

这些模型用于约束每个 Agent 的输出，避免后续 Graph / Workflow 依赖自然语言判断流程。

## 为什么需要 AgentOutput

多 Agent 工作流中，Agent 的输出会被后续节点消费。

例如 `RiskAgent` 执行后，Graph 需要判断下一步：

```text
decision = pass      -> SupervisorAgent
decision = retry     -> AnalysisAgent
decision = recollect -> ResearchAgent
```

如果只让模型返回一段文字，Graph 就必须解析自然语言，稳定性很差。因此每个 Agent 都应该返回结构化对象。

## 通用基类

所有输出都包含：

```text
agent_name
summary
```

- `agent_name`：产出该结果的 Agent 名称。
- `summary`：该 Agent 输出的简短摘要。

所有输出都支持：

```python
output.to_dict()
```

用于写入 `run_states.payload_json` 或 `run_events.payload_json`。

## TriageOutput

`TriageAgent` 的输出。

用途：

- 判断研究类型
- 识别研究对象
- 规划后续研究方向
- 判断需要哪些工具

核心字段：

```text
research_type
target
directions
constraints
required_tools
```

示例：

```json
{
  "agent_name": "TriageAgent",
  "summary": "识别为行业分析任务",
  "research_type": "industry_analysis",
  "target": "新能源汽车行业",
  "directions": [
    {
      "name": "竞争格局",
      "reason": "行业分析需要比较主要参与者"
    }
  ],
  "constraints": ["关注中国市场"],
  "required_tools": ["news_search", "industry_data_search"]
}
```

## ResearchOutput

`ResearchAgent` 的输出。

用途：

- 保存收集到的资料
- 记录关键材料
- 暴露资料缺口

核心字段：

```text
sources
key_materials
data_gaps
```

示例：

```json
{
  "agent_name": "ResearchAgent",
  "summary": "已收集行业新闻和数据摘要",
  "sources": [
    {
      "title": "新能源汽车行业月度数据",
      "source_type": "industry_data",
      "url": null,
      "published_at": "2026-05-01",
      "summary": "行业销量继续增长，但价格竞争加剧",
      "metadata": {}
    }
  ],
  "key_materials": ["行业销量增长", "价格竞争加剧"],
  "data_gaps": ["缺少近三年出口数据"]
}
```

## AnalysisOutput

`AnalysisAgent` 的输出。

用途：

- 形成核心观点
- 整理增长驱动
- 整理风险点
- 生成分析草稿

核心字段：

```text
findings
growth_drivers
risk_points
draft_report
```

## RiskOutput

`RiskAgent` 的输出。

用途：

- 检查分析草稿是否有证据支持
- 识别风险和资料缺口
- 决定 Graph 下一步流向

核心字段：

```text
decision
findings
reason
```

`decision` 只能是：

```text
pass
retry
recollect
```

含义：

```text
pass      -> 风险审查通过，进入 SupervisorAgent
retry     -> 分析逻辑需要修改，回到 AnalysisAgent
recollect -> 资料或证据不足，回到 ResearchAgent
```

## SupervisorOutput

`SupervisorAgent` 的输出。

用途：

- 汇总最终报告
- 给出关键结论
- 汇总风险提示
- 给出后续跟踪建议

核心字段：

```text
final_report
key_conclusions
risk_summary
follow_up_suggestions
```

## 当前设计取舍

当前版本使用 Pydantic `BaseModel` 和 `Enum`。

原因：

- Agent 输出需要强校验，避免 Graph 依赖自由文本。
- Tool 参数和 API 请求响应后续也会使用同一套校验方式。
- FastAPI 与 Pydantic 天然配合。
- `model_dump(mode="json")` 可以稳定生成可写入 SQLite JSON 字段的数据。

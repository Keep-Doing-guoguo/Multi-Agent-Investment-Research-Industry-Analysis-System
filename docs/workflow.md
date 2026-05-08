# Workflow Runner 说明

当前第一版使用手写 `ResearchWorkflowRunner`，不使用 LangGraph。

代码位置：

```text
app/workflow/runner.py
```

## 执行流程

当前主流程：

```text
TriageAgent
  -> ResearchAgent
  -> AnalysisAgent
  -> RiskAgent
      -> pass      -> SupervisorAgent
      -> retry     -> AnalysisAgent
      -> recollect -> ResearchAgent
```

## 为什么第一版不用 LangGraph

当前节点数量较少，分支规则明确。

手写 runner 的优点：

- 流程透明
- 测试简单
- 与现有 `MemoryManager`、`run_state`、`run_events` 直接集成
- 便于先跑通 MVP

后续如果需要并行 Research 节点、复杂子图、checkpoint、resume、人审节点，再迁移到 LangGraph。

## WorkflowConfig

当前配置：

```text
max_retry_count
max_recollect_count
max_total_steps
```

用途：

- `max_retry_count`：限制 RiskAgent 返回 `retry` 后回到 AnalysisAgent 的次数。
- `max_recollect_count`：限制 RiskAgent 返回 `recollect` 后回到 ResearchAgent 的次数。
- `max_total_steps`：限制整个 workflow 最大执行节点数，防止死循环。

## WorkflowResult

runner 完成后返回：

```text
session_id
run_id
status
final_report
steps_executed
```

## 失败处理

如果出现异常、未知节点、未知 `risk_decision` 或循环超限：

```text
1. run.status 更新为 failed
2. run_state.current_step 更新为 workflow_failed
3. 错误写入 run_state.errors
4. 写入 run_failed event
5. 重新抛出异常
```

## 与 SSE 的关系

Runner 本身不直接推送 SSE。

它通过 Agent 和 MemoryManager 写入：

```text
run_events
```

后续 SSE API 只需要持续读取 `run_events` 即可。

## 运行完整 Demo

先配置 `.env`：

```bash
cp .env.example .env
```

填写：

```text
LLM_PROVIDER=qwen
QWEN_API_KEY=你的 Qwen / DashScope API Key
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

运行默认示例：

```bash
python3 -m app.workflow.run_workflow_demo
```

传入自定义 query 和 topic：

```bash
python3 -m app.workflow.run_workflow_demo \
  --query "帮我分析中国光伏行业，重点看价格战和出口风险" \
  --topic "中国光伏行业"
```

运行后会输出：

```text
session_id
run_id
status
steps_executed
Final Report
```

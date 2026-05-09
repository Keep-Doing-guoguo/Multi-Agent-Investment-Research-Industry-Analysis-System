# 测试说明

当前测试使用普通函数调用和 `assert`，不依赖 `unittest` 或 `pytest`。

运行全部测试：

```bash
python3 tests/run_tests.py
```

当前覆盖范围：

- `SQLiteStore`
  - 初始化 SQLite schema
  - 创建 session 时初始化 summary 和 structured memory
  - 写入并读取 recent turns
  - 写入并读取 run state
  - 写入并读取 run events

- `MemoryManager`
  - `patch_structured_memory` 列表追加去重
  - `patch_run_state` 合并 run state
  - `build_context_for_agent` 组装 Agent 上下文
  - `emit_run_event` 记录 SSE 可消费事件

- `AgentOutput`
  - Pydantic 枚举序列化
  - 非法枚举值校验
  - 禁止额外字段

- `Tools`
  - 默认工具注册
  - 工具参数校验
  - 工具结果结构化返回

- `Agents`
  - TriageAgent 更新 `triage_result`
  - ResearchAgent 调用 mock tools 并更新 `research_result`
  - AnalysisAgent 更新 `analysis_result`
  - RiskAgent 更新 `risk_decision`
  - SupervisorAgent 写入 `final_report` 并完成 run

- `Workflow`
  - pass 分支完成 run
  - retry 分支回到 AnalysisAgent
  - recollect 分支回到 ResearchAgent
  - 循环超限后标记 run failed

- `API`
  - 创建研究任务
  - 查询 run
  - 查询 result
  - 查询 JSON events
  - 查询 SSE event stream

- `ResearchService`
  - SSE frame 格式化

测试数据库使用临时目录中的 SQLite 文件，不会写入 `data/app.sqlite3`。

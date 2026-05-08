# SQLite 表结构说明

本文档说明当前 SQLite 数据层的表结构。对应 SQL 文件为 `app/db/schema.sql`。

当前数据库围绕两个核心概念设计：

- `session`：一次用户会话，保存会话上下文和结构化记忆。
- `run`：一次具体研究任务，保存任务状态、执行事件和中间结果。

整体关系：

```text
sessions
  ├─ conversation_turns
  ├─ session_summaries
  ├─ structured_memories
  └─ runs
       ├─ run_states
       └─ run_events
```

## sessions

一次用户会话。

用户在同一个会话里可以连续提出研究请求、补充约束、追问结果。一个 `session` 可以包含多个 `run`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | `TEXT PRIMARY KEY` | 会话 ID |
| `title` | `TEXT` | 会话标题，可为空 |
| `status` | `TEXT` | 会话状态，默认 `active` |
| `created_at` | `TEXT` | 创建时间，ISO 格式 |
| `updated_at` | `TEXT` | 更新时间，ISO 格式 |

典型用途：

- 创建新会话
- 查询会话是否存在
- 展示历史会话列表
- 标记会话结束或归档

## conversation_turns

会话中的原始消息记录。

一条用户输入或系统回复都可以保存为一条 turn。该表用于保留最近对话、后续摘要压缩，以及调试对话上下文。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | 消息自增 ID |
| `session_id` | `TEXT` | 所属会话 ID |
| `role` | `TEXT` | 消息角色，例如 `user`、`assistant`、`system`、`agent` |
| `content` | `TEXT` | 消息内容 |
| `metadata_json` | `TEXT` | 附加信息，JSON 字符串 |
| `created_at` | `TEXT` | 创建时间，ISO 格式 |

外键：

- `session_id` 引用 `sessions.session_id`
- 删除 session 时级联删除对应 turns

索引：

- `idx_conversation_turns_session_created`

典型用途：

- 获取最近 6 条对话
- 为 summary compression 提供原始消息
- 回放用户和 Agent 的交互过程

## session_summaries

会话摘要。

当 `conversation_turns` 变多后，不应把所有原始消息都塞进模型上下文。较早消息可以压缩为 summary，保存在该表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | `TEXT PRIMARY KEY` | 所属会话 ID |
| `summary` | `TEXT` | 压缩后的会话摘要 |
| `updated_at` | `TEXT` | 更新时间，ISO 格式 |

外键：

- `session_id` 引用 `sessions.session_id`
- 删除 session 时级联删除 summary

典型用途：

- 构建 Agent 上下文
- 保存早期对话压缩结果
- 控制 prompt 长度

## structured_memories

结构化会话记忆。

该表不保存完整聊天记录，而是保存从会话中提炼出的稳定信息，例如研究范围、用户偏好、风险关注点、已接受结论和被否定假设。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | `TEXT PRIMARY KEY` | 所属会话 ID |
| `payload_json` | `TEXT` | 结构化记忆，JSON 字符串 |
| `updated_at` | `TEXT` | 更新时间，ISO 格式 |

外键：

- `session_id` 引用 `sessions.session_id`
- 删除 session 时级联删除 structured memory

推荐 payload 示例：

```json
{
  "research_topic": "新能源汽车行业",
  "confirmed_scope": "中国市场",
  "research_constraints": ["关注政策影响", "关注竞争格局"],
  "user_preferences": ["结论谨慎", "风险点单独列出"],
  "accepted_findings": [],
  "rejected_assumptions": [],
  "risk_focus": ["价格战", "补贴退坡", "产能过剩"]
}
```

典型用途：

- 为 Agent 提供稳定上下文
- 保存用户确认过的约束
- 避免每次从原始聊天记录里重新推断偏好

## runs

一次具体研究任务。

一个 session 里可以有多个 run。例如用户先分析行业，再继续分析某家公司，这可以是两个不同的 run。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | `TEXT PRIMARY KEY` | 任务 ID |
| `session_id` | `TEXT` | 所属会话 ID |
| `research_topic` | `TEXT` | 本次研究主题 |
| `status` | `TEXT` | 任务状态，默认 `pending` |
| `current_agent` | `TEXT` | 当前执行中的 Agent，可为空 |
| `retry_count` | `INTEGER` | 回到 Analysis 的次数 |
| `recollect_count` | `INTEGER` | 回到 Research 的次数 |
| `created_at` | `TEXT` | 创建时间，ISO 格式 |
| `updated_at` | `TEXT` | 更新时间，ISO 格式 |

外键：

- `session_id` 引用 `sessions.session_id`
- 删除 session 时级联删除 runs

索引：

- `idx_runs_session_created`

推荐 status：

```text
pending
running
completed
failed
cancelled
```

典型用途：

- 创建研究任务
- 查询任务整体状态
- 展示会话下的任务列表
- 判断当前任务是否完成

## run_states

run 的当前状态快照。

`run_states` 记录的是“当前最新状态”，适合状态查询和页面刷新恢复。它不同于 `run_events`，后者记录完整事件流。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | `TEXT PRIMARY KEY` | 所属任务 ID |
| `payload_json` | `TEXT` | 当前状态快照，JSON 字符串 |
| `updated_at` | `TEXT` | 更新时间，ISO 格式 |

外键：

- `run_id` 引用 `runs.run_id`
- 删除 run 时级联删除 run state

推荐 payload 示例：

```json
{
  "current_step": "risk_review",
  "triage_result": {},
  "research_result": {},
  "analysis_draft": "",
  "risk_findings": [],
  "final_report": "",
  "errors": [],
  "warnings": [],
  "decision": ""
}
```

典型用途：

- 查询当前 run 执行到哪一步
- 页面刷新后恢复任务状态
- 获取最终报告
- 保存 Agent 中间产物

## run_events

run 的执行事件流。

该表记录任务执行过程中的每个关键事件，后续 SSE 会主要消费这张表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `event_id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | 事件自增 ID |
| `run_id` | `TEXT` | 所属任务 ID |
| `event_type` | `TEXT` | 事件类型 |
| `agent_name` | `TEXT` | 相关 Agent 名称，可为空 |
| `payload_json` | `TEXT` | 事件内容，JSON 字符串 |
| `created_at` | `TEXT` | 创建时间，ISO 格式 |

外键：

- `run_id` 引用 `runs.run_id`
- 删除 run 时级联删除 events

索引：

- `idx_run_events_run_created`
- `idx_run_events_run_id`

推荐 event_type：

```text
run_created
agent_started
agent_completed
agent_failed
tool_started
tool_completed
tool_failed
risk_decision
run_completed
run_failed
```

典型用途：

- SSE 推送任务进度
- 查询某个 run 的执行历史
- 调试 Agent 执行过程
- 记录 retry、recollect、错误和最终完成事件

## Run、RunState、RunEvent 的区别

这三个对象都和任务执行有关，但职责不同。

| 对象 | 解决的问题 | 主要消费者 |
| --- | --- | --- |
| `runs` | 这个任务是什么，整体状态是什么 | 任务列表、任务详情 |
| `run_states` | 这个任务当前最新状态是什么 | 状态查询、页面刷新、结果接口 |
| `run_events` | 这个任务每一步发生了什么 | SSE、调试、执行回放 |

可以理解为：

```text
runs       = 任务主记录
run_states = 当前快照
run_events = 事件流水
```

## 当前设计取舍

当前版本采用“稳定实体拆表，变化内容 JSON 化”的策略：

- `sessions`、`conversation_turns`、`runs`、`run_events` 独立成表。
- `structured_memories.payload_json` 保存结构化记忆。
- `run_states.payload_json` 保存 Agent 中间状态。

这样做的原因是第一版重点在跑通多 Agent 工作流和会话记忆，不急于把所有业务字段拆成大量细表。后续如果需要更复杂的查询，再把 `risk_findings`、`tool_calls`、`agent_outputs` 等内容独立成表。

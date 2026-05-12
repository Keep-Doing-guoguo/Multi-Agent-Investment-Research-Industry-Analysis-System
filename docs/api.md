# API 说明

当前 API 使用 FastAPI。

入口：

```text
app/main.py
```

启动：

```bash
uvicorn app.main:app --reload
```

## 创建研究任务

```http
POST /api/research/runs
```

请求：

```json
{
  "session_id": "session_123",
  "query": "帮我分析中国新能源汽车行业，重点看价格战和出口风险",
  "topic": "中国新能源汽车行业",
  "title": "新能源汽车行业分析"
}
```

`session_id` 可选。不传时会创建一个新 session；传入时会复用已有 session，并把本次用户消息写入该 session 的聊天记录。

当前这个兼容入口仍是同步执行完整 workflow。请求返回时，run 通常已经完成或失败。

响应包含：

```text
run_id
session_id
research_topic
status
current_agent
retry_count
recollect_count
state
workflow
```

## 创建会话

```http
POST /api/sessions
```

请求：

```json
{
  "title": "新能源汽车行业分析"
}
```

响应返回：

```text
session_id
title
status
created_at
updated_at
```

## 在会话中发送消息并创建 Run

```http
POST /api/sessions/{session_id}/messages
```

请求：

```json
{
  "query": "继续分析出口风险，重点看欧洲市场",
  "topic": "中国新能源汽车行业"
}
```

`topic` 可选。不传时会优先使用 session title；如果 session title 也为空，则使用本次 `query` 作为研究主题。

该接口会：

```text
1. 将用户消息写入 conversation_turns
2. 基于同一个 session 创建新的 run_id
3. 后台执行 workflow
4. 立即返回 run 快照
5. 后续通过 run_id 监听 SSE 或查询结果
```

推荐前端主流程：

```text
POST /api/sessions
POST /api/sessions/{session_id}/messages
GET  /api/research/runs/{run_id}/events/stream
GET  /api/research/runs/{run_id}/result
```

## 查询任务状态

```http
GET /api/research/runs/{run_id}
```

返回 run 主记录和当前 `run_state` 快照。

## 查询最终结果

```http
GET /api/research/runs/{run_id}/result
```

返回：

```text
final_report
supervisor_result
risk_findings
```

## 查询任务事件

```http
GET /api/research/runs/{run_id}/events
```

可选 query 参数：

```text
after_event_id
limit
```

示例：

```http
GET /api/research/runs/run_123/events?after_event_id=10&limit=100
```

当前该接口是普通 JSON 事件列表。后续 SSE 会基于同一张 `run_events` 表扩展。

## SSE 事件流

```http
GET /api/research/runs/{run_id}/events/stream
```

可选 query 参数：

```text
after_event_id
poll_interval_seconds
max_idle_polls
```

示例：

```bash
curl -N "http://127.0.0.1:8000/api/research/runs/run_123/events/stream"
```

返回格式：

```text
id: 1
event: run_created
data: {"event_id":1,"run_id":"run_123","event_type":"run_created",...}

```

当前 SSE 实现会持续轮询 `run_events`。当 run 状态进入：

```text
completed
failed
cancelled
```

并且没有新的事件后，流会结束。

## 当前取舍

`POST /api/sessions/{session_id}/messages` 已经是后台执行 workflow，适合配合 SSE 展示进度。

`POST /api/research/runs` 保留为兼容入口，仍同步执行 workflow。

核心模型是：

```text
session 负责聊天记忆
run 负责单次执行状态
run_events 负责 SSE 进度事件
```

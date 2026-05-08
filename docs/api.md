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
  "query": "帮我分析中国新能源汽车行业，重点看价格战和出口风险",
  "topic": "中国新能源汽车行业",
  "title": "新能源汽车行业分析"
}
```

当前实现是同步执行完整 workflow。请求返回时，run 通常已经完成或失败。

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

当前 API 仍是同步执行 workflow。

下一步可以改成：

```text
POST /api/research/runs
  -> 创建 run
  -> 后台执行 workflow
  -> 立即返回 run_id
```

再配合：

```text
GET /api/research/runs/{run_id}/events
```

或 SSE 推送进度。当前 SSE endpoint 已经具备，后续需要把 `POST /runs` 改成后台执行，才能让前端在任务运行过程中实时看到事件。

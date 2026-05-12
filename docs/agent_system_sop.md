# 投研分析 Agent 系统开发 SOP

## 一、项目目标

构建一个：

- 多 Agent 协同
- 支持异步运行
- 支持 SSE 流式输出
- 支持事件追踪
- 支持 Session Memory
- 支持 Tool 调用
- 支持最终投研报告生成

的：

- 行业分析
- 公司分析
- 宏观分析
- 风险分析
- 新闻分析

企业级投研分析 Agent 系统。

系统核心目标：

```text
自动完成：
行业研究
公司分析
宏观分析
风险分析
新闻分析
最终报告聚合
```

---

## 二、整体系统架构

```text
Frontend / API Layer
        ↓
FastAPI Gateway
        ↓
LangGraph Runtime
        ↓
Supervisor / Planner Agent
        ↓
Multi Agents Parallel Execution
        ↓
Tools / Services Layer
        ↓
Aggregator Agent
        ↓
Final Report
```

---

## 三、系统核心模块

系统分为：

```text
1. API 接口层
2. Session / Run 管理层
3. Memory 模块
4. LangGraph Runtime
5. Multi-Agent 执行层
6. Tool / Service 层
7. Tracer / Event 层
8. Validation 层
9. Report 聚合层
```

---

## 四、接口层设计（API Layer）

### 1. generate

同步生成接口。

```http
POST /generate
```

作用：

```text
直接返回最终报告
```

适合：

- 小任务
- 快速问答
- 简单报告生成

### 2. runs

异步任务创建接口。

```http
POST /runs
```

返回：

```json
{
  "run_id": "run_xxx",
  "session_id": "session_xxx",
  "status": "running"
}
```

作用：

```text
创建一次完整 Agent 执行任务
```

### 3. runs/events

事件查询接口。

```http
GET /runs/{run_id}/events
```

作用：

```text
获取整个 Agent Runtime 的事件流
```

返回：

```json
[
  {
    "node": "MacroAgent",
    "event": "tool_started"
  }
]
```

### 4. runs/result

结果查询接口。

```http
GET /runs/{run_id}/result
```

返回：

```json
{
  "status": "completed",
  "report": "..."
}
```

### 5. runs/sse

SSE 实时输出接口。

```http
GET /runs/{run_id}/sse
```

作用：

```text
实时推送：
节点执行
Tool 调用
LLM 状态
报告生成过程
```

SSE 示例：

```text
event: node_started
data: {...}

event: tool_started
data: {...}

event: llm_chunk
data: {...}
```

---

## 五、数据库设计

仅保留两个核心表。

### 1. session 表

作用：

```text
管理长期会话记忆
```

字段：

| 字段 | 说明 |
| --- | --- |
| session_id | 会话 ID |
| conversation_summary | 历史压缩摘要 |
| recent_turns | 最近对话 |
| preferences | 用户偏好 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

### 2. run 表

作用：

```text
管理一次完整任务执行
```

字段：

| 字段 | 说明 |
| --- | --- |
| run_id | 运行 ID |
| session_id | 所属会话 |
| status | 当前状态 |
| current_node | 当前节点 |
| events | 执行事件 |
| result | 最终结果 |
| error_message | 错误信息 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

---

## 六、Memory 模块设计

### Session Memory

每个 Session：

```text
保留 recent_turns 最新 6 条
```

### Conversation Compress

当：

```text
recent_turns > 10
```

触发：

```text
compress_summary
```

压缩为：

```text
conversation_summary
```

并裁剪旧 turns。

### Memory 结构

```json
{
  "conversation_summary": "...",
  "recent_turns": []
}
```

---

## 七、Multi-Agent 架构设计

### 整体流程

```text
User Request
    ↓
Supervisor / Planner Agent
    ↓
Parallel Multi Agents
    ↓
Aggregator Agent
    ↓
Validator
    ↓
Final Report
```

---

## 八、Supervisor / Planner Agent

作用：

```text
任务理解
任务拆解
决定需要调用哪些 Agent
```

输入：

```text
用户问题
```

输出：

```json
{
  "need_macro": true,
  "need_company": true,
  "need_news": true
}
```

---

## 九、MacroAgent

负责：

```text
宏观经济分析
```

包含：

- 政策分析
- 利率分析
- 汇率分析
- 宏观数据分析

Tools：

```text
policy_search
macro_data_search
rate_fx_search
```

输出：

```text
宏观环境分析报告
```

---

## 十、CompanyAgent

负责：

```text
公司基本面分析
```

包含：

- 公告分析
- 财报分析
- 估值分析

Tools：

```text
announcement_search
financial_report_search
valuation_search
```

输出：

```text
公司基本面报告
```

---

## 十一、IndustryAgent

负责：

```text
行业分析
```

包含：

- 行业规模
- 行业格局
- 竞争分析
- 产业链分析

Tools：

```text
industry_data_search
competitor_search
supply_chain_search
```

输出：

```text
行业研究报告
```

---

## 十二、NewsAgent

负责：

```text
新闻与舆情分析
```

包含：

- 新闻检索
- 舆情分析
- 事件分析

Tools：

```text
news_search
sentiment_search
event_search
```

输出：

```text
新闻与市场情绪分析
```

---

## 十三、RiskAgent

负责：

```text
风险分析
```

包含：

- 法律风险
- 舆情风险
- 监管风险

Tools：

```text
litigation_search
negative_news_search
regulatory_penalty_search
```

输出：

```text
风险分析报告
```

---

## 十四、Aggregator Agent

作用：

```text
聚合所有 Agent 输出
```

最终生成：

```text
结构化投研报告
```

输出结构：

```text
1. 宏观环境
2. 行业分析
3. 公司分析
4. 财务分析
5. 新闻与舆情
6. 风险分析
7. 投资观点
8. 风险提示
9. 数据来源
```

---

## 十五、Tool 调用机制

### Tool 核心原则

```text
Tool 只负责数据获取
Agent 负责推理
```

Tool 负责：

- 数据查询
- 文档检索
- API 调用
- 数据获取

Agent 负责：

- 推理
- 任务决策
- Tool 选择
- 报告生成

Tool 示例：

```text
policy_search
macro_data_search
news_search
financial_report_search
valuation_search
```

---

## 十六、LangGraph Runtime 设计

### 必须使用 LangGraph 的原因

系统存在：

- 多节点
- 并行执行
- 状态流转
- 循环
- Fallback
- SSE
- Tracer
- 长生命周期任务

因此：

```text
必须使用 LangGraph
```

### Graph 结构

```text
START
  ↓
Planner
  ↓
Parallel Agents
  ↓
Aggregator
  ↓
Validator
  ↓
END
```

---

## 十七、循环机制（Loop）

生成最终报告后，进入：

```text
Validator
```

Validator 检查：

- 是否缺失数据
- 是否缺失风险项
- 是否缺少引用
- 是否报告不完整

若失败：

```text
重新调度对应 Agent
```

形成：

```text
Analysis Loop
```

---

## 十八、Tracer 系统

### Tracer 作用

用于：

- 节点追踪
- Tool 追踪
- LLM 追踪
- 错误追踪
- 性能追踪

### Tracer 数据结构

```json
{
  "run_id": "...",
  "node": "MacroAgent",
  "event": "tool_started",
  "latency_ms": 1000
}
```

---

## 十九、Emit / Event 系统

### Emit 作用

用于：

```text
SSE 实时推送
```

### Emit 示例

```json
{
  "type": "tool_started",
  "node": "CompanyAgent",
  "tool": "financial_report_search"
}
```

---

## 二十、Validation 模块

### 1. Request Validation

负责：

- 参数校验
- 城市校验
- 股票代码校验
- 时间范围校验
- Prompt Injection 过滤
- 空值处理

### 2. Output Validation

负责：

- 是否缺失报告
- 是否缺少引用
- 是否缺失风险分析
- 是否缺失关键字段

---

## 二十一、SSE 输出设计

SSE 推送：

```text
node_started
tool_started
tool_succeeded
llm_started
llm_chunk
llm_completed
validator_started
run_completed
```

---

## 二十二、推荐技术栈

### Backend

```text
FastAPI
LangGraph
PostgreSQL
Redis
```

### AI Model

```text
Qwen3
DeepSeek
GPT-4.1
```

### RAG

```text
Milvus
FAISS
bge-m3
```

### Streaming

```text
SSE
```

### Async Task

```text
Celery
Redis Queue
```

---

## 二十三、系统核心原则

### 1. Agent 负责推理

### 2. Tool 负责数据获取

### 3. LangGraph 负责状态流转

### 4. Session 管长期记忆

### 5. Run 管一次执行

### 6. 所有节点必须可追踪

### 7. 所有结果必须可回溯

---

## 二十四、最终目标

构建：

```text
企业级投研分析 Agent Runtime
```

而不是：

```text
简单聊天机器人
```

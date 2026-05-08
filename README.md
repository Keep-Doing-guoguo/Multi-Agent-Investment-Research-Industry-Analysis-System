# 多 Agent 项目产品需求分析

这份文档用于沉淀 **投研 / 行业分析系统** 的产品需求分析和技术路线设计。  
目标是把资料收集、分析建模、风险审查、结论汇总等过程拆成多个职责清晰的 Agent，形成一个工程化的多 Agent 研究系统。

---

## 一、项目名称

投研 / 行业分析系统

---

## 二、项目背景

传统投研分析流程通常需要大量人工收集和整理信息，存在以下问题：

- 新闻、公告、财报资料分散
- 研究视角不统一
- 风险因素容易遗漏
- 总结报告高度依赖个人经验
- 研究过程不易复盘和追踪

因此，适合引入多 Agent 协作模式，把研究任务拆成多个角色来协同完成。

---

## 三、产品目标

本项目目标是构建一个多 Agent 投研分析系统，实现以下能力：

- 自动识别研究主题
- 自动收集新闻、公告、财报和行业数据
- 自动提炼关键观点
- 自动识别风险点
- 自动生成研究摘要或行业分析报告
- 提供完整的研究过程记录和结论追踪

---

## 四、适用场景

适合以下研究任务：

- 公司基本面分析
- 行业趋势分析
- 政策影响分析
- 财报解读
- 风险事件跟踪
- 周报 / 月报自动生成

---

## 五、核心用户

- 研究员
- 投资经理
- 行业分析师
- 战略分析人员

---

## 六、核心输入与输出

### 输入

系统输入通常包括：

- 公司名称 / 行业名称 / 研究主题
- 新闻与公告数据
- 财报数据
- 行业指标数据
- 历史研究结论

### 输出

系统输出通常包括：

- 资料收集结果
- 关键观点摘要
- 风险点列表
- 研究结论
- 后续跟踪建议

---

## 七、多 Agent 技术路线

本项目建议严格按照以下 5 个 Agent 来拆分。

### 1. Triage Agent

负责研究任务拆解：

- 识别研究主题
- 判断研究对象类型
- 判断是公司分析、行业分析还是事件分析
- 规划后续需要收集的信息方向

例如：

- 公司基本面分析
- 行业趋势分析
- 政策影响分析
- 财报解读
- 风险事件跟踪

---

### 2. Research Agent

负责资料收集：

- 查新闻
- 查公告
- 查财报
- 查行业数据
- 查历史研究材料

它的目标不是直接下结论，而是：  
**收集可用的分析材料。**

---

### 3. Analysis Agent

负责整理和分析：

- 基于资料提炼核心观点
- 分析公司经营情况
- 分析行业竞争格局
- 分析增长点与风险点
- 形成结构化分析草稿

---

### 4. Risk Agent

负责风险审查：

- 检查结论是否有证据支持
- 识别潜在风险点
- 检查是否遗漏重大负面因素
- 判断是否存在结论过度推断

---

### 5. Supervisor Agent

负责总控：

- 汇总各 Agent 的输出
- 做最终结论归纳
- 输出最终研究摘要或行业分析报告

---

### 6. Memory Module

负责共享上下文与历史信息管理：

- 保存 `session memory`
- 保存 `recent turns`
- 保存 `conversation summary`
- 保存 `run state`
- 为各 Agent 提供统一读写接口
- 控制记忆压缩、长度上限和持久化

它的目标不是直接产出业务结果，而是：  
**为所有 Agent 提供可复用的上下文和状态支持。**

典型保存内容包括：

- 研究主题摘要
- 历史研究结论
- 风险偏好
- 历史跟踪记录
- 当前 run 中间状态

---

### 7. Tool Module

负责对外部能力和内部执行能力进行统一封装：

- 新闻检索工具
- 公告检索工具
- 财报检索工具
- 行业数据查询工具
- 图表生成工具
- 文本总结工具

它的目标不是做决策，而是：  
**为各 Agent 提供标准化、可观测、可校验的调用能力。**

---

### 8. Run / Workflow Module

负责整个多 Agent 系统的执行流转与运行管理：

- 创建 `session_id`
- 创建 `run_id`
- 组织当前这一次研究流程
- 记录执行状态
- 控制节点流转
- 控制重试、降级和人工复核
- 对外提供进度查询和最终结果查询

它的目标是：  
**把多个 Agent、Memory、Tool 串成一个可追踪、可恢复、可观测的运行系统。**

---

## 八、推荐工作流

推荐主流程如下：

```text
输入研究主题
  ↓
Triage Agent
  ↓
Research Agent
  ↓
Analysis Agent
  ↓
Risk Agent
  ↓
Supervisor Agent
  ↓
最终研究摘要 / 行业分析报告
```

如果需要加入循环修复，可扩展为：

```text
Research Agent
  ↓
Analysis Agent
  ↓
Risk Agent
  ├─ pass -> Supervisor Agent
  ├─ retry -> Analysis Agent
  └─ recollect -> Research Agent
```

---

## 九、推荐工程化能力

如果这个项目要做成工程化 Agent 系统，建议至少具备以下能力：

- `session_id`
- `run_id`
- `structured memory`
- `recent turns`
- `conversation summary`
- `run state`
- `validator`
- `retry / fallback`
- `SSE / polling`
- `observability`

---

## 十、数据库设计

建议至少包含以下数据实体：

- `sessions`
- `messages`
- `runs`
- `run_events`
- `tool_calls`
- `research_topics`
- `research_reports`
- `risk_findings`

推荐存储内容包括：

- 研究主题
- 资料来源摘要
- 分析草稿
- 风险审查结果
- 最终报告
- run 执行快照

推荐数据库选择：

- 本地开发：`SQLite`
- 中小型服务：`Postgres`
- 活跃状态和事件缓存：`Redis`

---

## 十一、接口设计

推荐至少提供以下接口。

### 1. 创建研究任务

```http
POST /api/research/runs
```

### 2. 查询任务状态

```http
GET /api/research/runs/{run_id}
```

### 3. 获取事件流

```http
GET /api/research/runs/{run_id}/events
```

### 4. 获取最终结果

```http
GET /api/research/runs/{run_id}/result
```

### 5. 继续追问或追加分析维度

```http
POST /api/research/follow-up
```

---

## 十二、可观测性设计

建议至少记录以下内容：

- `session_id`
- `run_id`
- 研究主题 ID
- 每个 Agent 的执行日志
- Tool 调用日志
- 模型调用日志
- 风险命中记录
- 平均研究耗时

---

## 十三、风控与安全设计

投研分析属于高敏感场景，必须补足以下能力：

- 数据来源可追踪
- 引用内容可追溯
- 结论与证据分离
- 防止模型无依据推断
- 对重大风险结论做人工复核
- 最大重试次数和死循环保护

---

## 十四、为什么这份设计符合工程化

这份多 Agent 方案不只是“让模型帮忙写分析摘要”，而是包含了完整工程要素：

- 明确的 Agent 分工
- 共享记忆模块
- 工具层封装
- run / workflow 执行模型
- 数据持久化设计
- 状态与事件流接口
- 可观测性设计
- 风险审查设计

因此它既适合作为产品需求分析，也适合作为后续工程实施蓝图。

---

## 当前开发状态

当前仓库已实现第一版后端 MVP：

- SQLite 数据层
- session memory
- run state / run events
- Pydantic Agent 输出模型
- mock research tools
- OpenAI-compatible LLM client，默认 Qwen
- 5 个 Agent
- 手写 WorkflowRunner
- FastAPI 接口

初始化数据库：

```bash
python3 -m app.db.init_db
```

配置 LLM：

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

运行完整 workflow demo：

```bash
python3 -m app.workflow.run_workflow_demo
```

启动 API：

```bash
uvicorn app.main:app --reload
```

运行测试：

```bash
python3 -m unittest discover -s tests
```

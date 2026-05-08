# Tools 层说明

当前 tools 层用于给后续 Agent 提供统一工具调用入口。

对应代码：

- `app/tools/registry.py`
- `app/tools/china_research_tools.py`
- `app/tools/mock_research_tools.py`

## 设计目标

Agent 不直接调用具体函数，而是通过 `ToolRegistry` 调用工具：

```python
result = registry.execute(
    "industry_data_search",
    {"query": "新能源汽车行业", "limit": 5},
)
```

这样后面把 mock 工具替换成真实 API 时，Agent 代码不需要大改。

## ToolRegistry

`ToolRegistry` 负责：

- 注册工具
- 列出可用工具
- 校验工具参数
- 执行工具 handler
- 返回统一的 `ToolResult`

当前错误类型：

```text
ToolNotFoundError
ToolArgumentError
ToolExecutionError
```

## 工具输入

当前搜索类工具统一使用：

```text
SearchToolArgs
```

字段：

```text
query: str
limit: int = 5
```

限制：

```text
query 最少 1 个字符
limit 范围 1 到 20
```

参数校验由 Pydantic 完成。

## 工具输出

所有工具统一返回：

```text
ToolResult
```

核心字段：

```text
tool_name
query
items
warnings
metadata
```

每个 item 使用：

```text
ToolItem
```

字段：

```text
title
source_type
summary
url
published_at
metadata
```

## 当前生产工具

生产入口使用：

```text
app/tools/china_research_tools.py
```

当前 4 个工具均使用国内来源：

```text
news_search                -> 东方财富
announcement_search        -> 巨潮资讯网
financial_report_search    -> 巨潮资讯网、东方财富
industry_data_search       -> 国家统计局、东方财富
```

其中 `news_search` 和部分检索路径支持可选东方财富 API key：

```text
EASTMONEY_APIKEY=
```

如果没有配置该 key，工具会跳过东方财富自然语言资讯检索，并返回结构化 warning。其他公开页面检索仍会继续尝试。

## Mock 工具

`app/tools/mock_research_tools.py` 仍然保留，主要用于单元测试和离线开发。

它也提供 4 个 mock research tools：

```text
news_search
announcement_search
financial_report_search
industry_data_search
```

这些工具返回确定性假数据。

## 后续替换真实工具

后续如果替换或增强真实数据源，优先保持工具名称和输出结构不变：

```text
news_search                -> 新闻 API / 搜索服务
announcement_search        -> 公告数据源
financial_report_search    -> 财报数据库 / 文件解析
industry_data_search       -> 行业指标数据源
```

只替换 handler 实现，不改 Agent 调用方式。

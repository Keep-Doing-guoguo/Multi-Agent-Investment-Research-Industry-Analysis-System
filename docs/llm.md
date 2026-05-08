# LLM 配置说明

当前项目使用 OpenAI-compatible SDK 调用 LLM，并用 Pydantic 校验结构化输出。

默认 provider 是 Qwen。

## 配置文件

复制 `.env.example` 为 `.env`：

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

如果需要切回 OpenAI：

```text
LLM_PROVIDER=openai
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=
```

`.env` 已加入 `.gitignore`，不会被提交。

## LLMClient

代码位置：

```text
app/llm/client.py
```

核心接口：

```python
generate_structured(
    system_prompt=...,
    user_prompt=...,
    output_model=TriageOutput,
)
```

LLM 返回 JSON 后，会使用 Pydantic 做校验：

```python
output_model.model_validate_json(content)
```

如果模型输出不符合 schema，会抛出错误，后续 workflow 可以据此重试或失败。

## 当前使用位置

当前已接入：

```text
TriageAgent
```

它会调用 LLM 输出 `TriageOutput`，然后写入：

```text
run_states.triage_result
structured_memories
run_events
```

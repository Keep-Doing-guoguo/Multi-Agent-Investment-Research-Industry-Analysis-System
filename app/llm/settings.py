from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    model: str
    base_url: str | None = None
    provider: str = "qwen"


def load_llm_settings(env_path: str | Path = DEFAULT_ENV_PATH) -> LLMSettings:
    load_env_file(Path(env_path))
    provider = os.getenv("LLM_PROVIDER", "qwen").strip().lower()

    if provider == "qwen":
        api_key = os.getenv("QWEN_API_KEY", "").strip()
        model = os.getenv("QWEN_MODEL", "qwen-plus").strip()
        base_url = os.getenv(
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).strip()
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    if not api_key:
        raise ValueError(
            f"{provider.upper()} API key is not configured. Add it to .env."
        )
    if not model:
        raise ValueError(f"{provider.upper()} model is not configured. Add it to .env.")
    return LLMSettings(
        api_key=api_key,
        model=model,
        base_url=base_url,
        provider=provider,
    )


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

from __future__ import annotations

from typing import Protocol, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.llm.settings import LLMSettings, load_llm_settings


T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        ...


class OpenAILLMClient:
    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or load_llm_settings()
        self.client = OpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
    ) -> T:
        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")

        try:
            return output_model.model_validate_json(content)
        except ValidationError as exc:
            raise ValueError(f"LLM output failed validation: {exc}") from exc

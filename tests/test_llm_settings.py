from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.llm.settings import load_llm_settings


class LLMSettingsTest(unittest.TestCase):
    def test_loads_qwen_settings_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("QWEN_API_KEY=test-key\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = load_llm_settings(env_path)

        self.assertEqual(settings.provider, "qwen")
        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.model, "qwen-plus")
        self.assertEqual(
            settings.base_url,
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def test_loads_openai_settings_when_provider_is_openai(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_PROVIDER=openai",
                        "OPENAI_API_KEY=openai-key",
                        "OPENAI_MODEL=gpt-test",
                        "OPENAI_BASE_URL=https://example.test/v1",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                settings = load_llm_settings(env_path)

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.api_key, "openai-key")
        self.assertEqual(settings.model, "gpt-test")
        self.assertEqual(settings.base_url, "https://example.test/v1")

    def test_rejects_unknown_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("LLM_PROVIDER=unknown\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    load_llm_settings(env_path)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.tools.mock_research_tools import build_default_tool_registry
from app.tools.registry import ToolArgumentError, ToolNotFoundError


class ToolRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_default_tool_registry()

    def test_default_registry_lists_research_tools(self) -> None:
        tool_names = {tool["name"] for tool in self.registry.list_tools()}

        self.assertEqual(
            tool_names,
            {
                "news_search",
                "announcement_search",
                "financial_report_search",
                "industry_data_search",
            },
        )

    def test_execute_returns_structured_tool_result(self) -> None:
        result = self.registry.execute(
            "industry_data_search",
            {"query": "新能源汽车行业", "limit": 1},
        )

        result_dict = result.to_dict()
        self.assertEqual(result_dict["tool_name"], "industry_data_search")
        self.assertEqual(result_dict["query"], "新能源汽车行业")
        self.assertEqual(len(result_dict["items"]), 1)
        self.assertEqual(result_dict["items"][0]["source_type"], "industry_data")

    def test_execute_rejects_unknown_tool(self) -> None:
        with self.assertRaises(ToolNotFoundError):
            self.registry.execute("unknown_tool", {"query": "test"})

    def test_execute_validates_arguments(self) -> None:
        with self.assertRaises(ToolArgumentError):
            self.registry.execute("news_search", {"query": "", "limit": 1})

        with self.assertRaises(ToolArgumentError):
            self.registry.execute("news_search", {"query": "test", "limit": 100})


if __name__ == "__main__":
    unittest.main()

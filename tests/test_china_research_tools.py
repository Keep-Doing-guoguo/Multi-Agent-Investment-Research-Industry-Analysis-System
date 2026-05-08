from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.tools.china_research_tools import (
    announcement_search,
    build_china_tool_registry,
    financial_report_search,
    industry_data_search,
    news_search,
)
from app.tools.registry import SearchToolArgs


class ChinaResearchToolsTest(unittest.TestCase):
    def test_registry_contains_real_china_tools(self) -> None:
        registry = build_china_tool_registry()
        self.assertEqual(
            {tool["name"] for tool in registry.list_tools()},
            {
                "news_search",
                "announcement_search",
                "financial_report_search",
                "industry_data_search",
            },
        )

    @patch("app.tools.china_research_tools._eastmoney_news_feed")
    @patch("app.tools.china_research_tools._eastmoney_financial_search")
    def test_news_search_uses_domestic_sources(self, mock_financial_search, mock_feed) -> None:
        mock_financial_search.return_value = ([], ["no api key"])
        mock_feed.return_value = (
            [
                {
                    "bad": "shape",
                }
            ],
            [],
        )
        # The feed helper should return ToolItem objects in real code. This branch validates
        # warnings and metadata without making a network call.
        mock_feed.return_value = ([], [])

        result = news_search(SearchToolArgs(query="新能源汽车", limit=2))

        self.assertEqual(result.tool_name, "news_search")
        self.assertEqual(result.metadata["sources"], ["东方财富"])
        self.assertIn("no api key", result.warnings)

    @patch("app.tools.china_research_tools._post_form")
    def test_announcement_search_parses_cninfo_announcements(self, mock_post_form) -> None:
        mock_post_form.return_value = {
            "announcements": [
                {
                    "announcementTitle": "2025年年度报告",
                    "adjunctUrl": "finalpage/2026-04-01/test.PDF",
                    "announcementTime": 1775001600000,
                    "secName": "测试公司",
                    "secCode": "000001",
                    "orgId": "gssz0000001",
                    "announcementId": "abc",
                }
            ]
        }

        result = announcement_search(SearchToolArgs(query="测试公司", limit=1))

        self.assertEqual(result.items[0].source_type, "announcement")
        self.assertEqual(result.items[0].metadata["source"], "巨潮资讯网")
        self.assertIn("static.cninfo.com.cn", result.items[0].url)

    @patch("app.tools.china_research_tools._eastmoney_financial_search")
    @patch("app.tools.china_research_tools._cninfo_announcement_search")
    def test_financial_report_search_combines_cninfo_and_eastmoney(
        self,
        mock_cninfo,
        mock_eastmoney,
    ) -> None:
        mock_cninfo.return_value = ([], ["cninfo warning"])
        mock_eastmoney.return_value = ([], ["eastmoney warning"])

        result = financial_report_search(SearchToolArgs(query="测试公司", limit=2))

        self.assertEqual(result.metadata["sources"], ["巨潮资讯网", "东方财富"])
        self.assertEqual(result.warnings, ["cninfo warning", "eastmoney warning"])

    @patch("app.tools.china_research_tools._eastmoney_news_feed")
    @patch("app.tools.china_research_tools._eastmoney_financial_search")
    @patch("app.tools.china_research_tools._stats_gov_search")
    def test_industry_data_search_uses_stats_and_eastmoney(
        self,
        mock_stats,
        mock_eastmoney,
        mock_feed,
    ) -> None:
        mock_stats.return_value = ([], ["stats warning"])
        mock_eastmoney.return_value = ([], ["eastmoney warning"])
        mock_feed.return_value = ([], ["feed warning"])

        result = industry_data_search(SearchToolArgs(query="新能源汽车", limit=2))

        self.assertEqual(result.metadata["sources"], ["国家统计局", "东方财富"])
        self.assertEqual(
            result.warnings,
            ["stats warning", "eastmoney warning", "feed warning"],
        )

    @patch.dict(os.environ, {"EASTMONEY_APIKEY": "test-key"}, clear=True)
    @patch("app.tools.china_research_tools._post_json")
    def test_eastmoney_api_key_path_returns_items(self, mock_post_json) -> None:
        mock_post_json.return_value = {
            "data": [
                {
                    "title": "新能源汽车新闻",
                    "summary": "国内市场竞争加剧",
                    "url": "https://example.com/news",
                    "date": "2026-05-01",
                }
            ]
        }

        result = news_search(SearchToolArgs(query="新能源汽车", limit=1))

        self.assertEqual(result.items[0].title, "新能源汽车新闻")
        self.assertEqual(result.items[0].metadata["source"], "东方财富")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from app.tools.registry import SearchToolArgs, ToolItem, ToolRegistry, ToolResult


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name="news_search",
        description="Search recent news related to a company, industry, policy, or risk event.",
        args_model=SearchToolArgs,
        handler=news_search,
    )
    registry.register(
        name="announcement_search",
        description="Search company announcements and regulatory disclosures.",
        args_model=SearchToolArgs,
        handler=announcement_search,
    )
    registry.register(
        name="financial_report_search",
        description="Search financial report summaries and key financial indicators.",
        args_model=SearchToolArgs,
        handler=financial_report_search,
    )
    registry.register(
        name="industry_data_search",
        description="Search industry indicators, market size, growth, and competitive data.",
        args_model=SearchToolArgs,
        handler=industry_data_search,
    )
    return registry


def news_search(args: SearchToolArgs) -> ToolResult:
    return ToolResult(
        tool_name="news_search",
        query=args.query,
        items=_limit_items(
            [
                ToolItem(
                    title=f"{args.query}相关新闻摘要",
                    source_type="news",
                    summary="行业新闻显示，市场竞争加剧，企业需要关注需求变化和利润率压力。",
                    published_at="2026-05-01",
                    metadata={"mock": True},
                ),
                ToolItem(
                    title=f"{args.query}风险事件跟踪",
                    source_type="news",
                    summary="近期报道集中在价格竞争、政策变化和供应链波动等因素。",
                    published_at="2026-05-02",
                    metadata={"mock": True},
                ),
            ],
            args.limit,
        ),
    )


def announcement_search(args: SearchToolArgs) -> ToolResult:
    return ToolResult(
        tool_name="announcement_search",
        query=args.query,
        items=_limit_items(
            [
                ToolItem(
                    title=f"{args.query}公告摘要",
                    source_type="announcement",
                    summary="公告材料显示，公司经营计划和资本开支安排需要结合行业景气度审慎评估。",
                    published_at="2026-04-28",
                    metadata={"mock": True},
                )
            ],
            args.limit,
        ),
    )


def financial_report_search(args: SearchToolArgs) -> ToolResult:
    return ToolResult(
        tool_name="financial_report_search",
        query=args.query,
        items=_limit_items(
            [
                ToolItem(
                    title=f"{args.query}财报指标摘要",
                    source_type="financial_report",
                    summary="财报摘要显示，收入增长与毛利率变化需要结合价格竞争和成本趋势分析。",
                    published_at="2026-03-31",
                    metadata={
                        "mock": True,
                        "metrics": {
                            "revenue_growth": "positive",
                            "gross_margin_pressure": "medium",
                        },
                    },
                )
            ],
            args.limit,
        ),
    )


def industry_data_search(args: SearchToolArgs) -> ToolResult:
    return ToolResult(
        tool_name="industry_data_search",
        query=args.query,
        items=_limit_items(
            [
                ToolItem(
                    title=f"{args.query}行业数据摘要",
                    source_type="industry_data",
                    summary="行业数据表明，需求仍有增长空间，但竞争格局和产能利用率是关键变量。",
                    published_at="2026-05-01",
                    metadata={
                        "mock": True,
                        "indicators": {
                            "demand_growth": "moderate",
                            "competition": "high",
                            "capacity_pressure": "medium",
                        },
                    },
                )
            ],
            args.limit,
        ),
    )


def _limit_items(items: list[ToolItem], limit: int) -> list[ToolItem]:
    return items[:limit]

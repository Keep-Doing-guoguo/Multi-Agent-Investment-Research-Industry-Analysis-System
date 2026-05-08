from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from app.tools.registry import SearchToolArgs, ToolItem, ToolRegistry, ToolResult


REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def build_china_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name="news_search",
        description="Search Chinese financial news from domestic sources.",
        args_model=SearchToolArgs,
        handler=news_search,
    )
    registry.register(
        name="announcement_search",
        description="Search listed-company announcements from CNINFO.",
        args_model=SearchToolArgs,
        handler=announcement_search,
    )
    registry.register(
        name="financial_report_search",
        description="Search financial reports and report-related announcements from CNINFO and Eastmoney.",
        args_model=SearchToolArgs,
        handler=financial_report_search,
    )
    registry.register(
        name="industry_data_search",
        description="Search domestic industry statistics and data-related materials.",
        args_model=SearchToolArgs,
        handler=industry_data_search,
    )
    return registry


def news_search(args: SearchToolArgs) -> ToolResult:
    items: list[ToolItem] = []
    warnings: list[str] = []

    eastmoney_items, eastmoney_warning = _eastmoney_financial_search(
        query=args.query,
        limit=args.limit,
        source_type="news",
    )
    items.extend(eastmoney_items)
    warnings.extend(eastmoney_warning)

    if len(items) < args.limit:
        feed_items, feed_warning = _eastmoney_news_feed(
            query=args.query,
            limit=args.limit - len(items),
        )
        items.extend(feed_items)
        warnings.extend(feed_warning)

    return ToolResult(
        tool_name="news_search",
        query=args.query,
        items=items[: args.limit],
        warnings=warnings,
        metadata={
            "sources": ["东方财富"],
            "real_data": True,
        },
    )


def announcement_search(args: SearchToolArgs) -> ToolResult:
    items, warnings = _cninfo_announcement_search(
        query=args.query,
        limit=args.limit,
        category=None,
    )
    return ToolResult(
        tool_name="announcement_search",
        query=args.query,
        items=items,
        warnings=warnings,
        metadata={
            "sources": ["巨潮资讯网"],
            "real_data": True,
        },
    )


def financial_report_search(args: SearchToolArgs) -> ToolResult:
    report_query = f"{args.query} 年度报告 季度报告 财务报告"
    items, warnings = _cninfo_announcement_search(
        query=report_query,
        limit=args.limit,
        category="category_ndbg_szsh;category_bndbg_szsh;category_yjdbg_szsh;category_sjdbg_szsh",
    )

    if len(items) < args.limit:
        eastmoney_items, eastmoney_warning = _eastmoney_financial_search(
            query=report_query,
            limit=args.limit - len(items),
            source_type="financial_report",
        )
        items.extend(eastmoney_items)
        warnings.extend(eastmoney_warning)

    return ToolResult(
        tool_name="financial_report_search",
        query=args.query,
        items=items[: args.limit],
        warnings=warnings,
        metadata={
            "sources": ["巨潮资讯网", "东方财富"],
            "real_data": True,
        },
    )


def industry_data_search(args: SearchToolArgs) -> ToolResult:
    items: list[ToolItem] = []
    warnings: list[str] = []

    stats_items, stats_warning = _stats_gov_search(args.query, args.limit)
    items.extend(stats_items)
    warnings.extend(stats_warning)

    if len(items) < args.limit:
        eastmoney_items, eastmoney_warning = _eastmoney_financial_search(
            query=f"{args.query} 行业 数据",
            limit=args.limit - len(items),
            source_type="industry_data",
        )
        items.extend(eastmoney_items)
        warnings.extend(eastmoney_warning)

    if len(items) < args.limit:
        feed_items, feed_warning = _eastmoney_news_feed(
            query=f"{args.query} 行业 数据",
            limit=args.limit - len(items),
            source_type="industry_data",
        )
        items.extend(feed_items)
        warnings.extend(feed_warning)

    return ToolResult(
        tool_name="industry_data_search",
        query=args.query,
        items=items[: args.limit],
        warnings=warnings,
        metadata={
            "sources": ["国家统计局", "东方财富"],
            "real_data": True,
        },
    )


def _eastmoney_financial_search(
    *,
    query: str,
    limit: int,
    source_type: str,
) -> tuple[list[ToolItem], list[str]]:
    api_key = os.getenv("EASTMONEY_APIKEY") or os.getenv("EASTMONEY_API_KEY")
    if not api_key:
        return [], ["EASTMONEY_APIKEY 未配置，跳过东方财富自然语言资讯检索。"]

    url = "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search"
    try:
        data = _post_json(
            url,
            headers={
                "Content-Type": "application/json",
                "apikey": api_key,
            },
            json_body={"query": query},
        )
    except requests.RequestException as exc:
        return [], [f"东方财富资讯检索失败: {exc}"]

    raw_items = _find_list_payload(data)
    items = [
        ToolItem(
            title=_clean_text(_pick(raw, "title", "Title", "name") or query),
            source_type=source_type,
            url=_pick(raw, "url", "Url", "link", "Link"),
            published_at=_normalize_date(_pick(raw, "published_at", "date", "time", "publishTime")),
            summary=_clean_text(
                _pick(raw, "summary", "content", "Content", "body", "text")
                or str(raw)[:300]
            ),
            metadata={"source": "东方财富", "raw": raw},
        )
        for raw in raw_items[:limit]
        if isinstance(raw, dict)
    ]
    return items, []


def _eastmoney_news_feed(
    *,
    query: str,
    limit: int,
    source_type: str = "news",
) -> tuple[list[ToolItem], list[str]]:
    if limit <= 0:
        return [], []
    url = (
        "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
        f"?client=web&biz=web_news_col&column=350&pageSize={min(max(limit * 3, 10), 50)}"
        f"&page=1&req_trace={int(time.time() * 1000)}"
    )
    try:
        data = _get_json(url)
    except requests.RequestException as exc:
        return [], [f"东方财富新闻列表获取失败: {exc}"]

    raw_items = _find_list_payload(data)
    keywords = _keywords(query)
    items: list[ToolItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        title = _clean_text(_pick(raw, "title", "newsTitle", "showTitle") or "")
        summary = _clean_text(_pick(raw, "digest", "summary", "content") or "")
        combined = f"{title} {summary}"
        if keywords and not any(keyword in combined for keyword in keywords):
            continue
        items.append(
            ToolItem(
                title=title or query,
                source_type=source_type,
                url=_pick(raw, "url", "newsUrl", "artUrl"),
                published_at=_normalize_date(_pick(raw, "showTime", "time", "publishTime")),
                summary=summary or title,
                metadata={"source": "东方财富", "raw": raw},
            )
        )
        if len(items) >= limit:
            break

    if not items and raw_items:
        for raw in raw_items[:limit]:
            if isinstance(raw, dict):
                title = _clean_text(_pick(raw, "title", "newsTitle", "showTitle") or query)
                items.append(
                    ToolItem(
                        title=title,
                        source_type=source_type,
                        url=_pick(raw, "url", "newsUrl", "artUrl"),
                        published_at=_normalize_date(_pick(raw, "showTime", "time", "publishTime")),
                        summary=_clean_text(_pick(raw, "digest", "summary", "content") or title),
                        metadata={"source": "东方财富", "raw": raw, "fallback_unfiltered": True},
                    )
                )
    return items, []


def _cninfo_announcement_search(
    *,
    query: str,
    limit: int,
    category: str | None,
) -> tuple[list[ToolItem], list[str]]:
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    form = {
        "pageNum": "1",
        "pageSize": str(min(max(limit, 1), 30)),
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": query,
        "secid": "",
        "category": category or "",
        "trade": "",
        "seDate": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    try:
        data = _post_form(
            url,
            form=form,
            headers={
                "Origin": "https://www.cninfo.com.cn",
                "Referer": "https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice",
            },
        )
    except requests.RequestException as exc:
        return [], [f"巨潮资讯公告检索失败: {exc}"]

    raw_items = data.get("announcements") or []
    items: list[ToolItem] = []
    for raw in raw_items[:limit]:
        title = _clean_text(re.sub(r"<[^>]+>", "", raw.get("announcementTitle", "")))
        adjunct_url = raw.get("adjunctUrl")
        published_at = _timestamp_to_date(raw.get("announcementTime"))
        items.append(
            ToolItem(
                title=title or query,
                source_type="announcement" if not category else "financial_report",
                url=urljoin("https://static.cninfo.com.cn/", adjunct_url) if adjunct_url else None,
                published_at=published_at,
                summary=f"{raw.get('secName', '')} {title}".strip(),
                metadata={
                    "source": "巨潮资讯网",
                    "sec_code": raw.get("secCode"),
                    "sec_name": raw.get("secName"),
                    "org_id": raw.get("orgId"),
                    "announcement_id": raw.get("announcementId"),
                },
            )
        )
    return items, []


def _stats_gov_search(query: str, limit: int) -> tuple[list[ToolItem], list[str]]:
    url = f"https://www.stats.gov.cn/search/s?qt={quote(query)}&siteCode=bm36000002&tab=all"
    try:
        html = _get_text(url)
    except requests.RequestException as exc:
        return [], [f"国家统计局检索失败: {exc}"]

    soup = BeautifulSoup(html, "html.parser")
    items: list[ToolItem] = []
    for anchor in soup.find_all("a", href=True):
        title = _clean_text(anchor.get_text(" ", strip=True))
        href = anchor["href"]
        if not title or len(title) < 4:
            continue
        if title in {item.title for item in items}:
            continue
        if query and not any(keyword in title for keyword in _keywords(query)):
            continue
        items.append(
            ToolItem(
                title=title,
                source_type="industry_data",
                url=urljoin("https://www.stats.gov.cn/", href),
                summary=title,
                metadata={"source": "国家统计局"},
            )
        )
        if len(items) >= limit:
            break
    return items, []


def _get_json(url: str) -> dict[str, Any]:
    response = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    json_body: dict[str, Any],
) -> dict[str, Any]:
    request_headers = _headers()
    request_headers.update(headers)
    response = requests.post(
        url,
        headers=request_headers,
        json=json_body,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _post_form(
    url: str,
    *,
    form: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = _headers()
    if headers:
        request_headers.update(headers)
    response = requests.post(
        url,
        headers=request_headers,
        data=form,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _get_text(url: str) -> str:
    response = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }


def _find_list_payload(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("data", "result", "items", "list", "news", "articles"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _find_list_payload(value)
            if nested:
                return nested
    return []


def _pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return _timestamp_to_date(value)
    text = str(value)
    match = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
    if match:
        return match.group(0).replace("/", "-")
    return text[:30]


def _timestamp_to_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        timestamp = int(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        return datetime.fromtimestamp(timestamp).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _keywords(query: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", query)
    return [token for token in tokens if token not in {"行业", "数据", "分析", "公司"}]

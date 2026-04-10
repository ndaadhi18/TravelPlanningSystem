"""
Web search places tool for PLANIT MCP server.

Uses Tavily as the primary provider and falls back to requests +
BeautifulSoup parsing when Tavily is unavailable.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient

from backend.schemas.itinerary import InsightCategory, LocalInsight, WebSearchInput
from backend.utils.logger import get_logger

logger = get_logger("mcp.tools.web_search_places")


_CATEGORY_KEYWORDS: list[tuple[InsightCategory, tuple[str, ...]]] = [
    (
        InsightCategory.HIDDEN_GEM,
        ("hidden gem", "offbeat", "lesser-known", "secret"),
    ),
    (
        InsightCategory.ATTRACTION,
        ("museum", "monument", "landmark", "tower", "cathedral"),
    ),
    (
        InsightCategory.RESTAURANT,
        ("restaurant", "cafe", "food", "dining", "bistro"),
    ),
    (
        InsightCategory.CULTURAL,
        ("culture", "history", "heritage", "art"),
    ),
    (
        InsightCategory.NIGHTLIFE,
        ("bar", "club", "nightlife", "pub"),
    ),
    (
        InsightCategory.SHOPPING,
        ("market", "shopping", "boutique", "mall"),
    ),
    (
        InsightCategory.NATURE,
        ("park", "garden", "trail", "beach", "lake"),
    ),
]


async def web_search_places_tool(input_params: WebSearchInput) -> list[LocalInsight]:
    """
    Search for places and local insights based on a destination query.

    Args:
        input_params: Structured web search parameters.

    Returns:
        A list of standardized LocalInsight objects.
    """
    logger.info(
        f"MCP Tool 'web_search_places' called: query='{input_params.query}', "
        f"depth={input_params.search_depth.value}, max_results={input_params.max_results}"
    )

    try:
        raw_results = _search_with_tavily(input_params)
    except Exception as tavily_error:
        logger.error(f"Tavily search failed, trying fallback: {tavily_error}")
        try:
            raw_results = _search_with_fallback(input_params)
        except Exception as fallback_error:
            logger.error(f"Fallback web search failed: {fallback_error}", exc_info=True)
            raise fallback_error from tavily_error

    insights = _normalize_results(raw_results, input_params.max_results)
    logger.info(f"Successfully parsed {len(insights)} local insights")
    return insights


def _search_with_tavily(input_params: WebSearchInput) -> list[dict[str, Any]]:
    """Primary provider flow using Tavily SDK."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured for Tavily search.")

    client = TavilyClient(api_key=api_key)
    kwargs: dict[str, Any] = {
        "query": input_params.query,
        "search_depth": input_params.search_depth.value,
        "max_results": input_params.max_results,
    }

    if input_params.include_domains:
        kwargs["include_domains"] = input_params.include_domains

    response = client.search(**kwargs)
    if not isinstance(response, dict):
        return []

    results = response.get("results", [])
    return results if isinstance(results, list) else []


def _search_with_fallback(input_params: WebSearchInput) -> list[dict[str, Any]]:
    """Fallback provider flow using HTTP + BeautifulSoup parsing."""
    response = requests.get(
        "https://duckduckgo.com/html/",
        params={"q": input_params.query},
        headers={"User-Agent": "planit-web-search/1.0"},
        timeout=10,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    entries: list[dict[str, Any]] = []

    for block in soup.select("div.result"):
        link = block.select_one("a.result__a") or block.select_one("a")
        snippet = block.select_one(".result__snippet")
        if not link:
            continue

        title = link.get_text(strip=True)
        url = _extract_real_url(link.get("href"))
        description = snippet.get_text(" ", strip=True) if snippet else title

        if not title and not description:
            continue

        entries.append(
            {
                "title": title,
                "url": url,
                "content": description,
            }
        )
        if len(entries) >= input_params.max_results:
            break

    return entries


def _extract_real_url(raw_url: Optional[str]) -> Optional[str]:
    """Extract actual destination URL from DuckDuckGo redirect links."""
    if not raw_url:
        return None
    if "duckduckgo.com/l/?" not in raw_url:
        return raw_url

    parsed = urlparse(raw_url)
    q = parse_qs(parsed.query)
    if "uddg" in q and q["uddg"]:
        return unquote(q["uddg"][0])
    return raw_url


def _normalize_results(raw_results: list[dict[str, Any]], max_results: int) -> list[LocalInsight]:
    """Normalize provider records into validated LocalInsight models."""
    insights: list[LocalInsight] = []
    seen_keys: set[tuple[str, str]] = set()

    for raw in raw_results:
        insight = _build_local_insight(raw)
        if insight is None:
            continue

        dedupe_key = (
            (insight.source_url or "").strip().lower(),
            insight.name.strip().lower(),
        )
        if dedupe_key in seen_keys:
            continue

        seen_keys.add(dedupe_key)
        insights.append(insight)

        if len(insights) >= max_results:
            break

    return insights


def _build_local_insight(raw: Any) -> Optional[LocalInsight]:
    """Convert a single provider item into LocalInsight."""
    if not isinstance(raw, dict):
        logger.warning(f"Skipping malformed search result type: {type(raw).__name__}")
        return None

    title = str(raw.get("title") or raw.get("name") or "").strip()
    description = str(
        raw.get("content") or raw.get("snippet") or raw.get("description") or ""
    ).strip()
    source_url = str(raw.get("url") or raw.get("source_url") or raw.get("link") or "").strip()

    if not title and source_url:
        title = source_url.split("/")[-1].replace("-", " ").replace("_", " ").strip() or "Untitled"
    if not title:
        title = "Untitled"
    if not description:
        description = "No description available."

    merged_text = f"{title}. {description}"
    category = _infer_category(merged_text)
    location = _extract_location(merged_text)
    rating = _parse_float(raw.get("rating"), minimum=0.0, maximum=5.0)
    estimated_cost = _extract_estimated_cost(merged_text)
    duration_hours = _extract_duration_hours(merged_text)

    try:
        return LocalInsight(
            name=title,
            category=category,
            description=description[:1000],
            location=location,
            estimated_cost=estimated_cost,
            duration_hours=duration_hours,
            source_url=source_url or None,
            rating=rating,
        )
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to parse individual web search result: {e}")
        return None


def _infer_category(text: str) -> InsightCategory:
    """Infer LocalInsight category from text keywords."""
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category
    return InsightCategory.ACTIVITY


def _extract_location(text: str) -> Optional[str]:
    """Best-effort location extraction from text."""
    match = re.search(r"\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", text)
    if not match:
        return None
    location = match.group(1).strip()
    return location if len(location) <= 80 else None


def _extract_estimated_cost(text: str) -> Optional[float]:
    """Best-effort extraction of a cost value from text."""
    match = re.search(r"(?:\$|€|£|₹)\s?(\d+(?:\.\d{1,2})?)", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if value >= 0 else None


def _extract_duration_hours(text: str) -> Optional[float]:
    """Best-effort extraction of duration in hours from text."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs)\b", text.lower())
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse_float(value: Any, minimum: float, maximum: float) -> Optional[float]:
    """Parse and clamp float values for optional numeric fields."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed

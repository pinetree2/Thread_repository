from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

import feedparser
import httpx

from app.tools.common import ExternalToolError, parse_published, period_to_days


AI_KEYWORDS = {
    "ai", "인공지능", "생성형", "llm", "gpt", "챗gpt", "chatgpt", "gemini",
    "claude", "딥시크", "deepseek", "agent", "에이전트", "openai", "앤트로픽",
    "머신러닝", "machine learning", "멀티모달", "로봇", "nvidia", "엔비디아",
}

AI_SEED_TOPICS = [
    "AI 에이전트",
    "생성형 AI",
    "멀티모달 AI",
    "온디바이스 AI",
    "AI 반도체",
]


def _is_ai_related(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in AI_KEYWORDS)


def _traffic_to_signal(value: str) -> int:
    match = re.search(r"([\d,.]+)\s*([KMB만천]?)", value or "")
    if not match:
        return 55
    number = float(match.group(1).replace(",", ""))
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "만": 10_000, "천": 1_000}.get(match.group(2), 1)
    volume = number * multiplier
    return int(min(100, 40 + 15 * max(0, len(str(int(volume))) - 2)))


class GoogleTrendsRssTool:
    """Reads Google's public Trending Now RSS export; no API key is required."""

    endpoint = "https://trends.google.com/trending/rss"
    namespace = "https://trends.google.com/trending/rss"

    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    def get_trends(self, country: str, category: str) -> list[dict]:
        try:
            response = httpx.get(
                self.endpoint,
                params={"geo": country},
                headers={"User-Agent": "Trend2Threads-AI/2.0"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalToolError(f"Google Trends RSS 요청 실패: {exc}") from exc

        feed = feedparser.parse(response.content)
        candidates: list[dict] = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            description = entry.get("summary", "")
            if category.lower() == "ai" and not _is_ai_related(f"{title} {description}"):
                continue
            traffic = entry.get("ht_approx_traffic", entry.get("approx_traffic", ""))
            candidates.append(
                {
                    "topic": title,
                    "source": "google_trends_rss",
                    "signal": _traffic_to_signal(traffic),
                    "mention_count": 1,
                    "source_diversity": 1,
                    "latest_at": parse_published(entry.get("published")).isoformat(),
                    "url": entry.get("link", ""),
                    "is_demo": False,
                }
            )
        return candidates


class GoogleNewsRssTool:
    """Searches Google News RSS to obtain current, keyless news evidence."""

    endpoint = "https://news.google.com/rss/search"

    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    def search(self, query: str, region: str = "GLOBAL", period: str = "14d", limit: int = 30) -> list[dict]:
        country = "US" if region == "GLOBAL" else region
        language = "ko" if region == "KR" else "en"
        days = period_to_days(period)
        params = {
            "q": f"{query} when:{days}d",
            "hl": f"{language}",
            "gl": country,
            "ceid": f"{country}:{language}",
        }
        try:
            response = httpx.get(
                self.endpoint,
                params=params,
                headers={"User-Agent": "Trend2Threads-AI/2.0"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalToolError(f"Google News RSS 요청 실패: {exc}") from exc

        feed = feedparser.parse(response.content)
        results: list[dict] = []
        for entry in feed.entries[:limit]:
            publisher = entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else ""
            published = parse_published(entry.get("published"))
            results.append(
                {
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "type": "news",
                    "publisher": publisher,
                    "published_at": published.isoformat(),
                    "description": entry.get("summary", ""),
                }
            )
        return results

    def discover_candidates(self, region: str, period: str) -> list[dict]:
        """Compare fixed AI subtopics by recent article volume and publisher diversity."""
        candidates = []
        for topic in AI_SEED_TOPICS:
            articles = self.search(topic, region=region, period=period, limit=30)
            publishers = Counter(item["publisher"] or "unknown" for item in articles)
            latest = max((item["published_at"] for item in articles), default=datetime.now(UTC).isoformat())
            candidates.append(
                {
                    "topic": topic,
                    "source": "google_news_rss",
                    "signal": min(100, 45 + len(articles) * 2),
                    "mention_count": len(articles),
                    "source_diversity": len(publishers),
                    "latest_at": latest,
                    "is_demo": False,
                }
            )
        return candidates

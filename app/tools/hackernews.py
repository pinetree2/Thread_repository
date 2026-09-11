from __future__ import annotations

import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import httpx

from app.models import TrendCandidate
from app.tools.common import ExternalToolError, period_to_days
from app.tools.topic_normalization import canonical_topic


HN_AI_PATTERN = re.compile(
    r"\b(?:ai|artificial intelligence|machine learning|llm|gpt(?:-?\d+(?:\.\d+)?)?|"
    r"openai|anthropic|claude|gemini|deepseek|qwen|mistral|mcp|model context protocol|"
    r"inference|neural networks?|ai agents?|agentic ai|rag)\b",
    flags=re.IGNORECASE,
)


class HackerNewsTool:
    """Collects AI stories and calculates engagement velocity from official HN data."""

    base_url = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, timeout: float = 15, max_items: int = 60):
        self.timeout = timeout
        self.max_items = max_items

    def _get_json(self, url: str):
        response = httpx.get(url, timeout=self.timeout, headers={"User-Agent": "Trend2Threads-AI/2.0"})
        response.raise_for_status()
        return response.json()

    def collect(self, period: str) -> list[TrendCandidate]:
        try:
            story_ids: list[int] = []
            for feed in ("topstories", "newstories", "beststories"):
                story_ids.extend(self._get_json(f"{self.base_url}/{feed}.json")[: self.max_items // 2])
            unique_ids = list(dict.fromkeys(story_ids))[: self.max_items]
            stories = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(self._get_json, f"{self.base_url}/item/{story_id}.json"): story_id
                    for story_id in unique_ids
                }
                for future in as_completed(futures):
                    try:
                        item = future.result()
                        if item:
                            stories.append(item)
                    except (httpx.HTTPError, ValueError):
                        continue
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalToolError(f"Hacker News API 요청 실패: {exc}") from exc

        cutoff = datetime.now(UTC) - timedelta(days=period_to_days(period))
        candidates: list[TrendCandidate] = []
        for item in stories:
            title = item.get("title", "")
            if item.get("type") != "story" or not HN_AI_PATTERN.search(title):
                continue
            published = datetime.fromtimestamp(item.get("time", 0), tz=UTC)
            if published < cutoff:
                continue
            score = max(int(item.get("score", 0)), 0)
            comments = max(int(item.get("descendants", 0)), 0)
            age_hours = max((datetime.now(UTC) - published).total_seconds() / 3600, 1)
            velocity = (score + comments * 1.5) / age_hours
            engagement = min(
                100.0,
                math.log1p(score) / math.log1p(600) * 45
                + math.log1p(comments) / math.log1p(300) * 30
                + math.log1p(velocity) / math.log1p(100) * 25,
            )
            story_url = item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}"
            candidates.append(
                TrendCandidate(
                    candidate_id=f"hn:{item['id']}",
                    topic=canonical_topic(title),
                    source="hackernews",
                    source_type="community",
                    title=title,
                    url=story_url,
                    published_at=published,
                    engagement=round(engagement, 1),
                    raw_score={"score": score, "comments": comments, "velocity_per_hour": round(velocity, 2)},
                    aliases=[title],
                    # HN links are user-submitted signals, not verified evidence.
                    official_source_url=None,
                    metadata={"hn_discussion_url": f"https://news.ycombinator.com/item?id={item['id']}"},
                )
            )
        return candidates

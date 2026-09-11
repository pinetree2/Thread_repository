from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.models import TrendCandidate
from app.tools.common import ExternalToolError, period_to_days
from app.tools.topic_normalization import canonical_topic


def _relative_date(value: str) -> datetime:
    value = (value or "").lower()
    match = re.search(r"(\d+)\s+(minute|hour|day|week|month|year)", value)
    if not match:
        return datetime.now(UTC)
    amount, unit = int(match.group(1)), match.group(2)
    days = {"minute": amount / 1440, "hour": amount / 24, "day": amount, "week": amount * 7, "month": amount * 30, "year": amount * 365}[unit]
    return datetime.now(UTC) - timedelta(days=days)


class SerpApiYouTubeTool:
    """Combines SerpAPI youtube search and youtube_video detail engines."""

    endpoint = "https://serpapi.com/search"

    def __init__(self, api_key: str, timeout: float = 15, max_details: int = 3):
        if not api_key:
            raise ValueError("SERPAPI_API_KEY가 필요합니다.")
        self.api_key = api_key
        self.timeout = timeout
        self.max_details = max_details

    def _request(self, params: dict) -> dict:
        try:
            response = httpx.get(
                self.endpoint,
                params={**params, "api_key": self.api_key, "output": "json"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise ExternalToolError(f"SerpAPI 오류: {payload['error']}")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalToolError(f"SerpAPI YouTube 요청 실패: {exc}") from exc

    def collect(self, period: str, region: str) -> list[TrendCandidate]:
        gl = "us" if region == "GLOBAL" else region.lower()
        search = self._request(
            {"engine": "youtube", "search_query": "AI OR LLM OR AI agents", "gl": gl, "hl": "en", "sp": "CAI="}
        )
        cutoff = datetime.now(UTC) - timedelta(days=period_to_days(period))
        results = search.get("video_results", [])
        candidates: list[TrendCandidate] = []
        for index, item in enumerate(results[:10]):
            video_id = item.get("video_id")
            if not video_id:
                continue
            published = _relative_date(item.get("published_date", ""))
            if published < cutoff:
                continue
            views = int(item.get("views") or 0)
            likes, comments = 0, 0
            if index < self.max_details:
                detail = self._request({"engine": "youtube_video", "v": video_id, "gl": gl, "hl": "en"})
                views = int(detail.get("extracted_views") or views)
                likes = int(detail.get("extracted_likes") or 0)
                comments = len(detail.get("comments", []))
                if detail.get("published_date"):
                    try:
                        published = datetime.strptime(detail["published_date"], "%b %d, %Y").replace(tzinfo=UTC)
                    except ValueError:
                        pass
            age_days = max((datetime.now(UTC) - published).total_seconds() / 86_400, 0.25)
            velocity = views / age_days
            engagement = min(
                100.0,
                math.log1p(views) / math.log1p(2_000_000) * 55
                + math.log1p(likes) / math.log1p(100_000) * 25
                + math.log1p(max(velocity, 0)) / math.log1p(1_000_000) * 20,
            )
            title = item.get("title") or "AI video"
            candidates.append(
                TrendCandidate(
                    candidate_id=f"youtube:{video_id}",
                    topic=canonical_topic(title),
                    source="youtube_serpapi",
                    source_type="video",
                    title=title,
                    url=item.get("link") or f"https://www.youtube.com/watch?v={video_id}",
                    published_at=published,
                    engagement=round(engagement, 1),
                    raw_score={
                        "views": views,
                        "likes": likes,
                        "comments_sampled": comments,
                        "view_velocity_per_day": round(velocity, 2),
                    },
                    aliases=[title],
                    metadata={"channel": (item.get("channel") or {}).get("name", ""), "video_id": video_id},
                )
            )
        return candidates


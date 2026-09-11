from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import httpx

from app.models import TrendCandidate
from app.tools.common import ExternalToolError, parse_published, period_to_days
from app.tools.topic_normalization import canonical_topic


class GitHubRepositorySearchTool:
    """Uses GitHub Search API; it does not pretend a GitHub Trending API exists."""

    endpoint = "https://api.github.com/search/repositories"

    def __init__(self, token: str | None = None, timeout: float = 15):
        self.token = token
        self.timeout = timeout

    def collect(self, period: str) -> list[TrendCandidate]:
        days = period_to_days(period)
        cutoff = datetime.now(UTC) - timedelta(days=days)
        query = f'("AI agent" OR LLM OR MCP OR inference OR RAG) in:name,description,topics created:>={cutoff.date().isoformat()}'
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Trend2Threads-AI/2.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = httpx.get(
                self.endpoint,
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 30},
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalToolError(f"GitHub Search API 요청 실패: {exc}") from exc

        candidates: list[TrendCandidate] = []
        for repo in items:
            created = parse_published(repo.get("created_at"))
            age_days = max((datetime.now(UTC) - created).total_seconds() / 86_400, 0.25)
            stars, forks = int(repo.get("stargazers_count", 0)), int(repo.get("forks_count", 0))
            star_velocity = stars / age_days
            engagement = min(
                100.0,
                math.log1p(stars) / math.log1p(5000) * 55
                + math.log1p(forks) / math.log1p(1000) * 20
                + math.log1p(star_velocity) / math.log1p(1000) * 25,
            )
            name = repo.get("name") or repo.get("full_name") or "AI repository"
            text = f"{name} {repo.get('description') or ''}"
            candidates.append(
                TrendCandidate(
                    candidate_id=f"github:{repo.get('id')}",
                    topic=canonical_topic(text),
                    source="github",
                    source_type="ecosystem",
                    title=repo.get("full_name") or name,
                    url=repo.get("html_url"),
                    published_at=created,
                    engagement=round(engagement, 1),
                    raw_score={
                        "stars": stars,
                        "forks": forks,
                        "star_velocity_per_day": round(star_velocity, 2),
                        "updated_at": repo.get("updated_at"),
                    },
                    aliases=[name, repo.get("full_name") or name],
                    official_source_url=repo.get("html_url"),
                    metadata={"topics": repo.get("topics", []), "language": repo.get("language")},
                )
            )
        return candidates

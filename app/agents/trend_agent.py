from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import Settings
from app.data.demo import demo_candidates
from app.graph.state import TrendThreadsState
from app.models import TrendCandidate
from app.tools.ai_model_watch import AIModelWatchTool
from app.tools.common import ExternalToolError
from app.tools.github_search import GitHubRepositorySearchTool
from app.tools.hackernews import HackerNewsTool
from app.tools.serpapi_youtube import SerpApiYouTubeTool


class TrendDiscoveryAgent:
    """Runs independent trend collectors and preserves partial successes."""

    name = "Trend Discovery Agent"
    allowed_tools = ("AIModelWatchTool", "HackerNewsTool", "GitHubRepositorySearchTool", "SerpApiYouTubeTool")

    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self, state: TrendThreadsState) -> dict:
        if state.get("demo_mode"):
            return {
                "trend_candidates": demo_candidates(),
                "data_mode": "demo",
                "available_sources": ["demo_fixture"],
                "successful_sources": ["demo_fixture"],
                "warnings": ["데모 모드: 트렌드 후보와 조사 자료는 명시적 fixture입니다."],
                "execution_trace": ["trend_discovery:demo_fixture"],
            }

        period, region = state["period"], state["region"]
        collectors = {
            "ai_model_watch": lambda: AIModelWatchTool(self.settings.request_timeout_seconds).collect(period),
            "hackernews": lambda: HackerNewsTool(
                self.settings.request_timeout_seconds, self.settings.max_hn_items
            ).collect(period),
            "github": lambda: GitHubRepositorySearchTool(
                self.settings.github_token, self.settings.request_timeout_seconds
            ).collect(period),
        }
        available = list(collectors)
        api_errors: list[dict[str, str]] = []
        if self.settings.has_serpapi_credentials:
            collectors["youtube_serpapi"] = lambda: SerpApiYouTubeTool(
                self.settings.serpapi_api_key or "",
                self.settings.request_timeout_seconds,
                self.settings.max_youtube_video_details,
            ).collect(period, region)
            available.append("youtube_serpapi")
        else:
            api_errors.append({"source": "youtube_serpapi", "reason": "SERPAPI_API_KEY not configured"})

        candidates: list[TrendCandidate] = []
        successful: list[str] = []
        with ThreadPoolExecutor(max_workers=len(collectors)) as executor:
            futures = {executor.submit(collector): name for name, collector in collectors.items()}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    candidates.extend(future.result())
                    successful.append(source)
                except (ExternalToolError, ValueError) as exc:
                    api_errors.append({"source": source, "reason": str(exc)})

        normalized = [candidate.model_dump(mode="json") for candidate in candidates]
        return {
            "trend_candidates": normalized,
            "data_mode": "live",
            "available_sources": available,
            "successful_sources": successful,
            "api_errors": api_errors,
            "execution_trace": [f"trend_discovery:{len(normalized)}_candidates:{len(successful)}_sources"],
        }

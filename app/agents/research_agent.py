from __future__ import annotations

from urllib.parse import urlparse

from app.config import Settings
from app.data.demo import demo_research
from app.graph.state import TrendThreadsState
from app.tools.common import ExternalToolError, clean_html, inside_period
from app.tools.naver_news import NaverNewsSearchTool
from app.tools.official_sources import OfficialSourceFetchTool
from app.tools.trends import GoogleNewsRssTool


OFFICIAL_DOMAINS = {
    "openai.com", "anthropic.com", "google.com", "blog.google", "developers.google.com",
    "microsoft.com", "nvidia.com", "meta.com", "ai.meta.com", "langchain.com",
    "docs.langchain.com", "github.com", "arxiv.org", "mistral.ai", "cohere.com",
}


def _classify_source(url: str, declared_type: str | None = None) -> str:
    if declared_type == "official":
        return "official"
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if host == "news.google.com":
        return "news"
    if any(host == domain or host.endswith(f".{domain}") for domain in OFFICIAL_DOMAINS):
        return "official"
    return "research" if host == "arxiv.org" else "news"


def _deduplicate(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = item.get("url") or item.get("title", "").lower()
        if key and key not in seen:
            seen.add(key)
            copy = dict(item)
            copy["type"] = _classify_source(copy.get("url", ""), copy.get("type"))
            unique.append(copy)
    return unique


def _claim_from_source(source: dict) -> str:
    title = clean_html(source.get("title", ""))
    description = clean_html(source.get("description", ""))
    return title if title else description[:180]


class ResearchAgent:
    """Turns a trend signal into evidence; trend posts are never facts themselves."""

    name = "Research Agent"
    allowed_tools = ("OfficialSourceFetchTool", "GoogleNewsRssTool", "NaverNewsSearchTool (KR only)")

    def __init__(self, settings: Settings, google_news: GoogleNewsRssTool):
        self.settings = settings
        self.google_news = google_news

    def __call__(self, state: TrendThreadsState) -> dict:
        retry = state.get("research_retry_count", 0)
        if state.get("demo_mode"):
            sources, facts = demo_research(state["selected_topic"], retry)
            return {
                "sources": sources,
                "raw_facts": facts,
                "available_sources": ["demo_research"],
                "successful_sources": ["demo_research"],
                "execution_trace": [f"research:demo:retry_{retry}"],
            }

        topic = state["selected_topic"]
        query = topic if retry == 0 else f"{topic} official announcement release"
        sources: list[dict] = []
        api_errors: list[dict[str, str]] = []
        successful: list[str] = []

        # Only AI Model Watch's provider source_url is pre-qualified as an
        # official lead. HN/YouTube popularity links remain trend signals only.
        official_tool = OfficialSourceFetchTool(self.settings.request_timeout_seconds)
        for candidate in state.get("selected_cluster", {}).get("candidates", []):
            official_url = candidate.get("official_source_url")
            if candidate.get("source") != "ai_model_watch" or not official_url:
                continue
            try:
                official = official_tool.fetch(official_url, candidate["title"])
                official["published_at"] = candidate.get("published_at")
                sources.append(official)
                if "official_sources" not in successful:
                    successful.append("official_sources")
            except ExternalToolError as exc:
                api_errors.append({"source": "official_sources", "reason": str(exc)})

        if state["region"] == "KR" and self.settings.has_naver_credentials:
            try:
                naver = NaverNewsSearchTool(
                    self.settings.naver_client_id or "",
                    self.settings.naver_client_secret or "",
                    self.settings.request_timeout_seconds,
                )
                sources.extend(naver.search(query, display=50, sort="date"))
                successful.append("naver_news")
            except ExternalToolError as exc:
                api_errors.append({"source": "naver_news", "reason": str(exc)})
        elif state["region"] == "KR":
            api_errors.append({"source": "naver_news", "reason": "NAVER_CLIENT_ID/SECRET not configured"})

        try:
            sources.extend(self.google_news.search(query, state["region"], state["period"], limit=30))
            successful.append("google_news_rss")
        except ExternalToolError as exc:
            api_errors.append({"source": "google_news_rss", "reason": str(exc)})

        sources = [item for item in _deduplicate(sources) if inside_period(item.get("published_at"), state["period"])]
        sources = sources[:20]
        facts = [
            {"claim": _claim_from_source(source), "source_indexes": [index]}
            for index, source in enumerate(sources)
            if _claim_from_source(source)
        ]
        return {
            "sources": sources,
            "raw_facts": facts,
            "available_sources": ["official_sources", "google_news_rss"] + (["naver_news"] if state["region"] == "KR" else []),
            "successful_sources": successful,
            "api_errors": api_errors,
            "execution_trace": [f"research:live:{len(sources)}_sources:retry_{retry}"],
        }

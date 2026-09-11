from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    naver_client_id: str | None = os.getenv("NAVER_CLIENT_ID") or None
    naver_client_secret: str | None = os.getenv("NAVER_CLIENT_SECRET") or None
    serpapi_api_key: str | None = os.getenv("SERPAPI_API_KEY") or None
    github_token: str | None = os.getenv("GITHUB_TOKEN") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
    fact_check_threshold: float = float(os.getenv("FACT_CHECK_THRESHOLD", "0.80"))
    max_research_retry: int = int(os.getenv("MAX_RESEARCH_RETRY", "2"))
    max_hn_items: int = int(os.getenv("MAX_HN_ITEMS", "60"))
    max_youtube_video_details: int = int(os.getenv("MAX_YOUTUBE_VIDEO_DETAILS", "3"))
    max_content_retry: int = int(os.getenv("MAX_CONTENT_RETRY", "2"))
    threads_access_token: str | None = os.getenv("THREADS_ACCESS_TOKEN") or None
    threads_user_id: str | None = os.getenv("THREADS_USER_ID") or None
    threads_graph_api_version: str | None = os.getenv("THREADS_GRAPH_API_VERSION") or None
    cron_secret: str | None = os.getenv("CRON_SECRET") or None
    data_dir: str = os.getenv("DATA_DIR", ".data")

    @property
    def has_naver_credentials(self) -> bool:
        return bool(self.naver_client_id and self.naver_client_secret)

    @property
    def has_llm_credentials(self) -> bool:
        return self.llm_provider == "openai" and bool(self.openai_api_key)

    @property
    def has_serpapi_credentials(self) -> bool:
        return bool(self.serpapi_api_key)

    @property
    def has_threads_credentials(self) -> bool:
        # Threads user access token identifies the app-scoped user; publishing
        # can safely use Meta's documented /me alias.
        return bool(self.threads_access_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()

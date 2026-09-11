from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.tools.common import ExternalToolError


class OfficialSourceFetchTool:
    """Checks provider URLs supplied by the trusted AI Model Watch catalog."""

    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    def fetch(self, url: str, event_title: str) -> dict:
        if urlparse(url).scheme != "https":
            raise ExternalToolError("공식 Source는 HTTPS URL이어야 합니다.")
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": "Trend2Threads-AI/2.0", "Accept": "text/html,application/json"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalToolError(f"공식 Source 확인 실패: {exc}") from exc
        return {
            "title": event_title,
            "url": str(response.url),
            "type": "official",
            "publisher": urlparse(str(response.url)).netloc.removeprefix("www."),
            "published_at": None,
            "description": "AI Model Watch가 연결한 Provider 공식 자료 URL의 응답을 Research 단계에서 확인했습니다.",
        }

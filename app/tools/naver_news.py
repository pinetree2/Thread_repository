from __future__ import annotations

import httpx

from app.tools.common import ExternalToolError, clean_html, parse_published


class NaverNewsSearchTool:
    """Official Naver Search News API client.

    Documentation: https://developers.naver.com/docs/serviceapi/search/news/news.md
    """

    endpoint = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self, client_id: str, client_secret: str, timeout: float = 15):
        if not client_id or not client_secret:
            raise ValueError("NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET이 필요합니다.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout

    def search(self, query: str, display: int = 50, sort: str = "date") -> list[dict]:
        display = max(1, min(display, 100))
        if sort not in {"date", "sim"}:
            raise ValueError("sort는 'date' 또는 'sim'이어야 합니다.")
        try:
            response = httpx.get(
                self.endpoint,
                params={"query": query, "display": display, "start": 1, "sort": sort},
                headers={
                    "X-Naver-Client-Id": self.client_id,
                    "X-Naver-Client-Secret": self.client_secret,
                    "User-Agent": "Trend2Threads-AI/2.0",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalToolError(f"Naver News API 요청 실패: {exc}") from exc

        return [
            {
                "title": clean_html(item.get("title", "")),
                "url": item.get("originallink") or item.get("link", ""),
                "type": "news",
                "publisher": "",
                "published_at": parse_published(item.get("pubDate")).isoformat(),
                "description": clean_html(item.get("description", "")),
            }
            for item in payload.get("items", [])
        ]

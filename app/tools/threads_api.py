from __future__ import annotations

from typing import Any

import httpx

from app.tools.common import ExternalToolError


class ThreadsPublishingTool:
    """Meta 공식 Threads API의 text container -> publish -> permalink 흐름."""

    def __init__(self, access_token: str, user_id: str, timeout: float = 15, api_version: str | None = None):
        version = f"/{api_version.strip('/')}" if api_version else ""
        self.base_url = f"https://graph.threads.com{version}"
        self.access_token = access_token
        # A Threads username (for example tappaws0.0) is not a Graph user ID.
        # The official API supports /me for the user represented by the token,
        # which avoids username/app-scoped-ID confusion.
        self.user_id = "me"
        self.timeout = timeout

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload: Any = response.json()
            return str(payload.get("error", {}).get("message") or payload)
        except Exception:
            return f"HTTP {response.status_code}"

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/{path.lstrip('/')}",
            data={**data, "access_token": self.access_token},
            timeout=self.timeout,
        )
        if response.is_error:
            raise ExternalToolError(self._error_message(response))
        return response.json()

    def publish_text(self, full_text: str) -> dict[str, str | None]:
        if not full_text.strip() or len(full_text) > 500:
            raise ValueError("Threads text는 1~500자여야 합니다")

        container = self._post(
            f"{self.user_id}/threads",
            {"media_type": "TEXT", "text": full_text},
        )
        container_id = str(container.get("id", ""))
        if not container_id:
            raise ExternalToolError("Threads container id가 응답에 없습니다")

        published = self._post(
            f"{self.user_id}/threads_publish",
            {"creation_id": container_id},
        )
        post_id = str(published.get("id", ""))
        if not post_id:
            raise ExternalToolError("Threads post id가 응답에 없습니다")

        permalink: str | None = None
        try:
            response = httpx.get(
                f"{self.base_url}/{post_id}",
                params={"fields": "id,permalink", "access_token": self.access_token},
                timeout=self.timeout,
            )
            if not response.is_error:
                permalink = response.json().get("permalink")
        except httpx.HTTPError:
            # 게시 성공은 유지하고 permalink 조회 실패만 허용한다.
            permalink = None

        return {"publish_status": "published", "threads_post_id": post_id, "threads_permalink": permalink}

from __future__ import annotations

from app.config import Settings
from app.graph.state import TrendThreadsState
from app.tools.threads_api import ThreadsPublishingTool


class ThreadsPublisherAgent:
    """승인된 글만 Publishing Tool에 전달하며 다른 파이프라인을 재실행하지 않는다."""

    name = "Threads Publisher Agent"
    allowed_tools = ("ThreadsPublishingTool",)

    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self, state: TrendThreadsState) -> dict:
        if not state.get("approved") or state.get("approval_decision") != "approve":
            return {
                "publish_status": "failed",
                "status": "publish_failed",
                "api_errors": [{"source": "threads", "reason": "명시적 사용자 승인이 없습니다"}],
                "execution_trace": ["threads_publish:blocked_without_approval"],
            }
        if not self.settings.has_threads_credentials:
            return {
                "publish_status": "configuration_required",
                "status": "publish_failed",
                "api_errors": [
                    {"source": "threads", "reason": "THREADS_ACCESS_TOKEN이 설정되지 않았습니다"}
                ],
                "execution_trace": ["threads_publish:configuration_required"],
            }

        try:
            tool = ThreadsPublishingTool(
                self.settings.threads_access_token or "",
                self.settings.threads_user_id or "",
                self.settings.request_timeout_seconds,
                self.settings.threads_graph_api_version,
            )
            result = tool.publish_text((state.get("thread_post") or {}).get("full_text", ""))
            return {**result, "status": "published", "execution_trace": ["threads_publish:published"]}
        except Exception as exc:
            return {
                "publish_status": "failed",
                "status": "publish_failed",
                "api_errors": [{"source": "threads", "reason": str(exc)}],
                "execution_trace": ["threads_publish:failed"],
            }

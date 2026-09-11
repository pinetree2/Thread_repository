from __future__ import annotations

from typing import Literal

from app.graph.state import TrendThreadsState


def route_trend_score(state: TrendThreadsState) -> Literal["research", "rejected"]:
    has_topic = bool(state.get("selected_topic"))
    qualified = state.get("trend_score", 0) >= state.get("min_trend_score", 0)
    return "research" if has_topic and qualified else "rejected"


def route_fact_check(state: TrendThreadsState) -> Literal["research", "writer", "insufficient"]:
    if state.get("confidence", 0) >= state.get("fact_check_threshold", 0.80):
        return "writer"
    if state.get("research_retry_count", 0) <= state.get("max_research_retry", 2):
        return "research"
    # 신뢰도 기준을 끝내 충족하지 못하면 근거 수와 관계없이 생성하지 않는다.
    return "insufficient"


def route_content_review(state: TrendThreadsState) -> Literal["approval", "writer", "failed"]:
    review = state.get("review") or {}
    if not review.get("needs_revision", True):
        return "approval"
    if state.get("content_retry_count", 0) <= state.get("max_content_retry", 2):
        return "writer"
    return "failed"


def route_approval(state: TrendThreadsState) -> Literal["publish", "review", "reject"]:
    decision = state.get("approval_decision")
    if decision == "approve":
        return "publish"
    if decision == "edit":
        return "review"
    return "reject"

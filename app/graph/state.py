from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_unique_strings(left: list[str], right: list[str]) -> list[str]:
    return list(dict.fromkeys((left or []) + (right or [])))


def merge_unique_errors(left: list[dict[str, str]], right: list[dict[str, str]]) -> list[dict[str, str]]:
    merged = (left or []) + (right or [])
    return list({(item.get("source", ""), item.get("reason", "")): item for item in merged}.values())


class TrendThreadsState(TypedDict, total=False):
    # Input: API/CLI가 만들고 Discovery, Writer가 소비한다.
    region: str
    language: str
    category: str
    period: str
    min_trend_score: int
    content_style: str
    auto_publish: bool
    demo_mode: bool
    run_id: str

    # Trend: Discovery -> Normalizer -> Analyzer -> score router.
    trend_candidates: list[dict[str, Any]]
    normalized_candidates: list[dict[str, Any]]
    trend_clusters: list[dict[str, Any]]
    selected_cluster: dict[str, Any]
    selected_topic: str
    trend_score: float
    trend_reason: str
    score_breakdown: dict[str, Any]

    # Evidence: Research -> Fact Check -> confidence router.
    sources: list[dict[str, Any]]
    raw_facts: list[dict[str, Any]]
    verified_facts: list[str]
    confidence: float
    research_retry_count: int
    max_research_retry: int
    fact_check_threshold: float

    # Threads content: Writer -> Review -> Human Approval.
    thread_post: dict[str, str] | None
    hashtags: list[str]
    review: dict[str, Any] | None
    content_retry_count: int
    max_content_retry: int
    approval_decision: str | None
    approved: bool

    # Publishing: Publisher Tool 결과만 갱신한다.
    publish_status: str
    threads_post_id: str | None
    threads_permalink: str | None

    # 운영 메타데이터. Reducer는 Loop 중 동일 메시지 중복을 제거한다.
    status: str
    data_mode: str
    available_sources: Annotated[list[str], merge_unique_strings]
    successful_sources: Annotated[list[str], merge_unique_strings]
    api_errors: Annotated[list[dict[str, str]], merge_unique_errors]
    warnings: Annotated[list[str], merge_unique_strings]
    execution_trace: Annotated[list[str], operator.add]
    error: str | None


def initial_state(
    payload: dict[str, Any],
    max_research_retry: int,
    fact_check_threshold: float = 0.80,
    max_content_retry: int = 2,
) -> TrendThreadsState:
    """graph.invoke()에 전달할 예측 가능한 전체 초기 상태를 만든다."""
    return TrendThreadsState(
        **payload,
        trend_candidates=[],
        normalized_candidates=[],
        trend_clusters=[],
        selected_cluster={},
        selected_topic="",
        trend_score=0.0,
        trend_reason="",
        score_breakdown={},
        sources=[],
        raw_facts=[],
        verified_facts=[],
        confidence=0.0,
        research_retry_count=0,
        max_research_retry=max_research_retry,
        fact_check_threshold=fact_check_threshold,
        thread_post=None,
        hashtags=[],
        review=None,
        content_retry_count=0,
        max_content_retry=max_content_retry,
        approval_decision=None,
        approved=False,
        publish_status="not_ready",
        threads_post_id=None,
        threads_permalink=None,
        status="running",
        data_mode="demo" if payload.get("demo_mode") else "live",
        available_sources=[],
        successful_sources=[],
        api_errors=[],
        warnings=[],
        execution_trace=[],
        error=None,
    )

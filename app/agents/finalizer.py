from __future__ import annotations

from app.graph.state import TrendThreadsState


def finalize_rejected(state: TrendThreadsState) -> dict:
    return {
        "status": "no_qualified_trend",
        "publish_status": "not_ready",
        "warnings": ["최소 Trend Score를 충족하는 후보가 없습니다."],
        "execution_trace": ["finalize:no_qualified_trend"],
    }


def finalize_insufficient(state: TrendThreadsState) -> dict:
    return {
        "status": "insufficient_evidence",
        "publish_status": "not_ready",
        "warnings": ["재조사 한도 내에서 콘텐츠 생성에 필요한 검증 근거를 확보하지 못했습니다."],
        "execution_trace": ["finalize:insufficient_evidence"],
    }


def finalize_content_review_failed(state: TrendThreadsState) -> dict:
    return {
        "status": "content_review_failed",
        "publish_status": "not_ready",
        "warnings": ["최대 수정 횟수 내에 게시 품질 기준을 충족하지 못했습니다."],
        "execution_trace": ["finalize:content_review_failed"],
    }


def finalize_user_rejected(state: TrendThreadsState) -> dict:
    return {
        "status": "rejected_by_user",
        "publish_status": "rejected",
        "execution_trace": ["finalize:rejected_by_user"],
    }

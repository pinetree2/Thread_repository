from __future__ import annotations

import re

from app.agents.threads_writer import THREADS_TEXT_LIMIT
from app.graph.state import TrendThreadsState
from app.models import ContentReview, ThreadPost


CLICKBAIT_TERMS = ("충격", "무조건", "100% 확실", "역대급", "세상이 끝", "you won't believe")
CASUAL_STYLE_VIOLATIONS = (
    "여러분", "습니다", "합니다", "됩니다", "해요", "예요", "이에요", "인가요", "하시나요", "바랍니다"
)


def _duplicate_line_ratio(text: str) -> float:
    lines = [line.strip().lower() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return 1.0
    return 1 - (len(set(lines)) / len(lines))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text)}


def _body_is_grounded(body: str, facts: list[str], topic: str) -> bool:
    """출처 표기를 제외한 본문이 전체 근거 및 주제와 충분히 연결되는지 확인한다."""
    claims = [
        line.lstrip("•- ").strip()
        for line in body.splitlines()
        if line.lstrip("•- ").strip() and not line.lstrip("•- ").strip().startswith("출처:")
    ]
    evidence_tokens = _tokens(" ".join([topic, *facts]))
    claim_tokens = _tokens(" ".join(claims))
    if not claims or not evidence_tokens or not claim_tokens:
        return False
    overlap = claim_tokens & evidence_tokens
    # 한국어는 조사와 어미가 붙어 전체 토큰 비율이 낮아질 수 있다.
    # 핵심 토큰이 두 개 이상 겹치고 일정 비율 이상이면 근거 기반으로 본다.
    return len(overlap) >= 2 and len(overlap) / len(claim_tokens) >= 0.08


class ContentReviewAgent:
    """게시 제한, 숫자 근거, 출처 수, 과장·중복을 결정론적으로 검사한다."""

    name = "Content Review Agent"
    allowed_tools = ("Pydantic validation", "grounding rules")

    def __call__(self, state: TrendThreadsState) -> dict:
        issues: list[str] = []
        post_data = state.get("thread_post") or {}
        facts = state.get("verified_facts", [])
        sources = state.get("sources", [])

        try:
            post = ThreadPost.model_validate(post_data)
            text = post.full_text
        except Exception as exc:
            text = str(post_data.get("full_text", ""))
            issues.append(f"게시글 schema 오류: {exc}")

        topic = state.get("selected_topic", "")
        number_evidence = [topic, *facts]
        number_evidence.extend(
            f"{source.get('title', '')} {source.get('publisher', '')} {source.get('published_at', '')}"
            for source in sources
        )
        fact_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", " ".join(number_evidence)))
        post_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", text))
        factual_post_numbers = {
            value for value in post_numbers if len(value) > 1 or "." in value or "," in value
        }
        body = str(post_data.get("body", ""))
        factually_grounded = (
            bool(facts)
            and factual_post_numbers <= fact_numbers
            and _body_is_grounded(body, facts, topic)
        )
        if not factually_grounded:
            issues.append("검증 사실에 없는 숫자가 있거나 검증 사실이 없습니다.")

        independent_publishers = {source.get("publisher") or source.get("url") for source in sources}
        official_sources = sum(source.get("type") == "official" for source in sources)
        source_supported = (
            (len(independent_publishers) >= 2 and len(facts) >= 2)
            or (official_sources >= 1 and len(facts) >= 1)
        )
        if not source_supported:
            issues.append("독립된 Fact Source 또는 검증 사실이 부족합니다.")
        elif len(independent_publishers) < 2:
            issues.append("보조 뉴스 Source 장애로 공식 Source 1개 fallback을 사용했습니다.")

        within_limit = 0 < len(text) <= THREADS_TEXT_LIMIT
        if not within_limit:
            issues.append(f"Threads 본문이 {THREADS_TEXT_LIMIT}자 제한을 충족하지 않습니다.")

        no_clickbait = not any(term.lower() in text.lower() for term in CLICKBAIT_TERMS)
        if not no_clickbait:
            issues.append("과도한 단정 또는 클릭베이트 표현이 있습니다.")

        casual_consistent = True
        if state.get("language") == "ko" and state.get("content_style") == "threads_casual":
            casual_consistent = not any(term in text for term in CASUAL_STYLE_VIOLATIONS)
            if not casual_consistent:
                issues.append("Threads Casual 글에 존댓말 또는 격식체가 섞여 있습니다.")

        low_duplication = _duplicate_line_ratio(text) <= 0.25
        if not low_duplication:
            issues.append("중복 표현이 많습니다.")

        readable = 3 <= len([line for line in text.splitlines() if line.strip()]) <= 12
        if not readable:
            issues.append("Threads에 적합한 줄바꿈 구조가 아닙니다.")

        checks = [
            factually_grounded,
            source_supported,
            within_limit,
            no_clickbait,
            low_duplication,
            readable,
            casual_consistent,
        ]
        quality_score = round(sum(checks) / len(checks), 2)
        # 현재 운영 모드에서는 검수 결과를 기록하되 검수 실패가 Human Approval을
        # 막지 않도록 한다. 실제 게시 여부는 반드시 승인 단계에서 결정된다.
        needs_revision = False
        review = ContentReview(
            factually_grounded=factually_grounded,
            source_supported=source_supported,
            quality_score=quality_score,
            needs_revision=needs_revision,
            issues=issues,
        )
        update: dict = {
            "review": review.model_dump(),
            "execution_trace": [f"content_review:{'fail' if needs_revision else 'pass'}:{quality_score}"],
        }
        if needs_revision:
            update["content_retry_count"] = state.get("content_retry_count", 0) + 1
        return update

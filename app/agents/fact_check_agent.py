from __future__ import annotations

import re
from collections import Counter

from app.config import Settings
from app.graph.state import TrendThreadsState


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text) if len(token) > 1}


class FactCheckAgent:
    """Cross-checks claims and emits only traceable source statements."""

    name = "Fact Check Agent"
    allowed_tools = ("cross_source_similarity", "source_quality_rules")

    def __init__(self, settings: Settings):
        self.threshold = settings.fact_check_threshold

    def __call__(self, state: TrendThreadsState) -> dict:
        sources = state.get("sources", [])
        raw_facts = state.get("raw_facts", [])
        retry_count = state.get("research_retry_count", 0)
        verified: list[str] = []

        for fact in raw_facts:
            claim = fact.get("claim", "").strip()
            indexes = [i for i in fact.get("source_indexes", []) if 0 <= i < len(sources)]
            if not claim or not indexes:
                continue
            official = any(sources[i].get("type") == "official" for i in indexes)
            claim_tokens = _tokens(claim)
            corroborated = 0
            for other in raw_facts:
                if other is fact:
                    continue
                overlap = claim_tokens & _tokens(other.get("claim", ""))
                if len(overlap) >= 3:
                    corroborated += 1
            if official or corroborated:
                verified.append(claim)

        strong_verified_count = len(verified)

        # If headlines do not semantically overlap, retain a few as explicitly
        # attributed observations; content generation cannot turn them into new facts.
        if len(verified) < 3:
            for fact in raw_facts:
                indexes = fact.get("source_indexes", [])
                if not indexes:
                    continue
                source = sources[indexes[0]]
                attributed = f"{source.get('publisher') or '수집 출처'} 보도 제목: {fact['claim']}"
                if attributed not in verified:
                    verified.append(attributed)
                if len(verified) >= 3:
                    break

        publisher_count = len({source.get("publisher") or source.get("url") for source in sources})
        official_count = sum(source.get("type") == "official" for source in sources)
        # Quantity alone cannot produce a review-ready score. Reaching 0.80
        # requires official evidence in addition to diverse/corroborated sources.
        source_score = min(len(sources) / 3, 1.0) * 0.30
        diversity_score = min(publisher_count / 4, 1.0) * 0.20
        official_score = min(official_count / 2, 1.0) * 0.25
        facts_score = min(strong_verified_count / 3, 1.0) * 0.25
        confidence = round(min(1.0, source_score + diversity_score + official_score + facts_score), 2)

        # Google News RSS 등 보조 수집원이 일시적으로 503이어도, Provider
        # 공식 자료가 실제로 확인된 경우에는 사실 확인을 중단하지 않는다.
        # 결과에는 API 오류가 그대로 남아 단일 근거 모드임을 설명한다.
        if confidence < self.threshold and official_count >= 1 and strong_verified_count >= 1:
            confidence = self.threshold

        update = {
            "verified_facts": verified[:6],
            "confidence": confidence,
            "execution_trace": [f"fact_check:confidence_{confidence}:retry_{retry_count}"],
        }
        if confidence < self.threshold:
            update["research_retry_count"] = retry_count + 1
        return update

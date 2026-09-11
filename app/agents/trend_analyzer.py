from __future__ import annotations

from app.graph.state import TrendThreadsState
from app.tools.common import period_to_days
from app.tools.scoring import calculate_trend_score


class TrendAnalyzerAgent:
    """Ranks normalized clusters using code-only, auditable signal math."""

    name = "Trend Analyzer Agent"
    allowed_tools = ("calculate_trend_score",)

    def __call__(self, state: TrendThreadsState) -> dict:
        ranked = []
        for cluster in state.get("trend_clusters", []):
            score, breakdown = calculate_trend_score(cluster, period_to_days(state["period"]))
            ranked.append((score, breakdown, cluster))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            return {
                "selected_topic": "",
                "selected_cluster": {},
                "trend_score": 0.0,
                "score_breakdown": {},
                "trend_reason": "정상 수집된 Source에서 분석 가능한 AI 트렌드 후보를 찾지 못했습니다.",
                "execution_trace": ["trend_analysis:no_candidate"],
            }

        score, breakdown, selected = ranked[0]
        available = [
            f"{name} {details['value']:.0f}"
            for name, details in breakdown.items()
            if isinstance(details, dict) and details.get("available")
        ]
        missing = [
            name for name, details in breakdown.items()
            if isinstance(details, dict) and not details.get("available")
        ]
        reason = f"{', '.join(available)} 신호를 결측 가중치 재정규화 방식으로 계산했습니다."
        if missing:
            reason += f" 미수집 신호({', '.join(missing)})는 0점이 아니라 계산 가중치에서 제외했습니다."
        return {
            "selected_topic": selected["topic"],
            "selected_cluster": selected,
            "trend_score": score,
            "score_breakdown": breakdown,
            "execution_trace": [f"trend_analysis:selected:{selected['topic']}:{score}"],
            "trend_reason": reason,
        }

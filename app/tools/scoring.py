from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.tools.common import parse_published


BASE_WEIGHTS = {
    "recency": 0.20,
    "community": 0.25,
    "video": 0.25,
    "ecosystem": 0.15,
    "cross_source": 0.15,
}


def _recency_score(candidates: list[dict], period_days: int) -> float:
    values = []
    for candidate in candidates:
        published = parse_published(candidate.get("published_at"))
        age_days = max(0.0, (datetime.now(UTC) - published).total_seconds() / 86_400)
        values.append(max(0.0, 100.0 * (1 - age_days / max(period_days, 1))))
    return max(values, default=0.0)


def _max_engagement(candidates: list[dict], source_types: set[str]) -> float | None:
    values = [float(item.get("engagement", 0)) for item in candidates if item.get("source_type") in source_types]
    return max(values) if values else None


def calculate_trend_score(cluster: dict[str, Any], period_days: int = 14) -> tuple[float, dict[str, Any]]:
    """Calculate a reproducible score and reweight missing dimensions."""
    candidates = cluster.get("candidates", [])
    unique_sources = {item.get("source") for item in candidates if item.get("source")}
    unique_types = {item.get("source_type") for item in candidates if item.get("source_type")}
    values: dict[str, float | None] = {
        "recency": _recency_score(candidates, period_days) if candidates else None,
        "community": _max_engagement(candidates, {"community"}),
        "video": _max_engagement(candidates, {"video"}),
        "ecosystem": _max_engagement(candidates, {"technology", "ecosystem"}),
        "cross_source": min(100.0, len(unique_sources) / 3 * 100.0) if candidates else None,
    }
    available_weight = sum(BASE_WEIGHTS[name] for name, value in values.items() if value is not None)
    breakdown: dict[str, Any] = {}
    score = 0.0
    for name, base_weight in BASE_WEIGHTS.items():
        value = values[name]
        effective_weight = base_weight / available_weight if value is not None and available_weight else 0.0
        contribution = (value or 0.0) * effective_weight
        score += contribution
        breakdown[name] = {
            "value": None if value is None else round(value, 1),
            "base_weight": base_weight,
            "effective_weight": round(effective_weight, 4),
            "contribution": round(contribution, 1),
            "available": value is not None,
        }
    confirmation_cap = 69.0 if len(unique_sources) <= 1 else 89.0 if len(unique_sources) == 2 else 100.0
    score = min(score, confirmation_cap)
    breakdown["source_count"] = len(unique_sources)
    breakdown["source_types"] = sorted(unique_types)
    breakdown["formula"] = "weighted mean with missing-signal renormalization"
    breakdown["confirmation_cap"] = confirmation_cap
    return round(max(0.0, min(score, 100.0)), 1), breakdown

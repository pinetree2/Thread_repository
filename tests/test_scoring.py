from datetime import UTC, datetime

import pytest

from app.tools.scoring import BASE_WEIGHTS, calculate_trend_score


def candidate(source: str, source_type: str, engagement: float) -> dict:
    return {
        "source": source,
        "source_type": source_type,
        "engagement": engagement,
        "published_at": datetime.now(UTC).isoformat(),
    }


def test_cluster_score_is_normalized_and_explainable():
    cluster = {
        "candidates": [
            candidate("hackernews", "community", 90),
            candidate("youtube", "video", 85),
            candidate("modelwatch", "technology", 88),
        ]
    }
    score, parts = calculate_trend_score(cluster, 14)
    assert 0 <= score <= 100
    assert score >= 80
    assert set(BASE_WEIGHTS) <= set(parts)
    assert parts["source_count"] == 3


def test_missing_youtube_weight_is_renormalized_not_zeroed():
    cluster = {
        "candidates": [
            candidate("hackernews", "community", 90),
            candidate("modelwatch", "technology", 90),
        ]
    }
    score, parts = calculate_trend_score(cluster, 14)
    assert parts["video"]["available"] is False
    assert parts["video"]["effective_weight"] == 0
    effective_sum = sum(parts[name]["effective_weight"] for name in BASE_WEIGHTS)
    assert effective_sum == pytest.approx(1.0, abs=0.001)
    assert score > 70


def test_empty_cluster_returns_zero():
    score, _ = calculate_trend_score({"candidates": []}, 14)
    assert score == 0


def test_single_source_cluster_cannot_cross_default_threshold():
    cluster = {"candidates": [candidate("hackernews", "community", 100)]}
    score, parts = calculate_trend_score(cluster, 14)
    assert score == 69
    assert parts["confirmation_cap"] == 69

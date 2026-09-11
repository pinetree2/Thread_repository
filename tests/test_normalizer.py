from datetime import UTC, datetime

from app.agents.trend_normalizer import TrendNormalizerAgent


def item(candidate_id: str, topic: str, source: str, source_type: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "topic": topic,
        "source": source,
        "source_type": source_type,
        "title": topic,
        "url": "https://example.com/item",
        "published_at": datetime.now(UTC).isoformat(),
        "engagement": 80,
        "raw_score": {},
    }


def test_equivalent_agent_topics_are_clustered():
    state = {
        "trend_candidates": [
            item("1", "AI Agent", "hackernews", "community"),
            item("2", "Agentic AI", "github", "ecosystem"),
        ]
    }
    result = TrendNormalizerAgent()(state)
    assert len(result["normalized_candidates"]) == 2
    assert len(result["trend_clusters"]) == 1
    assert set(result["trend_clusters"][0]["sources"]) == {"hackernews", "github"}

from app.graph.routers import route_content_review, route_fact_check, route_trend_score


def test_score_router_uses_request_threshold():
    assert route_trend_score({"selected_topic": "AI", "trend_score": 70, "min_trend_score": 70}) == "research"
    assert route_trend_score({"selected_topic": "AI", "trend_score": 69.9, "min_trend_score": 70}) == "rejected"


def test_fact_router_retries_then_stops():
    assert route_fact_check({"confidence": 0.79, "research_retry_count": 1, "max_research_retry": 2}) == "research"
    assert route_fact_check({"confidence": 0.79, "research_retry_count": 3, "max_research_retry": 2}) == "insufficient"
    state = {"confidence": 0.79, "research_retry_count": 3, "max_research_retry": 2, "sources": [{}, {}], "verified_facts": ["fact"]}
    assert route_fact_check(state) == "insufficient"
    assert route_fact_check({"confidence": 0.80, "research_retry_count": 0, "max_research_retry": 2}) == "writer"


def test_content_review_router_is_bounded():
    assert route_content_review({"review": {"needs_revision": False}}) == "approval"
    assert route_content_review({"review": {"needs_revision": True}, "content_retry_count": 1, "max_content_retry": 2}) == "writer"
    assert route_content_review({"review": {"needs_revision": True}, "content_retry_count": 3, "max_content_retry": 2}) == "failed"

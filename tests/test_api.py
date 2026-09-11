from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def demo_payload():
    return {
        "region": "GLOBAL",
        "language": "ko",
        "category": "AI",
        "period": "14d",
        "min_trend_score": 70,
        "content_style": "informative",
        "auto_publish": False,
        "demo_mode": True,
    }


def test_health_reports_threads_integration():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == "Trend2Threads AI"
    assert payload["graph_compiled"] is True
    assert "threads_publish_configured" in payload["integrations"]
    assert "pexels_configured" not in payload["integrations"]


def test_demo_analyze_waits_for_human_and_can_reject():
    response = client.post("/api/analyze", json=demo_payload())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "awaiting_approval"
    assert payload["thread_post"]
    assert len(payload["thread_post"]["full_text"]) <= 500
    assert payload["review"]["quality_score"] >= 0.8
    assert payload["auto_publish"] is False

    rejected = client.post(f"/api/runs/{payload['run_id']}/decision", json={"action": "reject"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected_by_user"


def test_decision_rejects_unknown_run():
    response = client.post("/api/runs/not-found/decision", json={"action": "approve"})
    assert response.status_code == 404

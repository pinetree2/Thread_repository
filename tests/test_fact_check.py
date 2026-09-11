from app.agents.fact_check_agent import FactCheckAgent
from app.config import Settings


def test_news_quantity_alone_cannot_be_review_ready():
    sources = [
        {"title": f"기사 {i}", "url": f"https://news.example/{i}", "type": "news", "publisher": f"언론사 {i}"}
        for i in range(6)
    ]
    facts = [
        {"claim": f"AI 에이전트 관련 공통 핵심 소식 {i}", "source_indexes": [i]}
        for i in range(6)
    ]
    result = FactCheckAgent(Settings())(
        {"sources": sources, "raw_facts": facts, "research_retry_count": 0}
    )
    assert result["confidence"] < 0.80
    assert result["research_retry_count"] == 1

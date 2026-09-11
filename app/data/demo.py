from __future__ import annotations

from datetime import UTC, datetime, timedelta


def demo_candidates() -> list[dict]:
    """Stable presentation fixtures. These are not represented as live API data."""
    now = datetime.now(UTC)
    return [
        {
            "candidate_id": "demo-model-agent",
            "topic": "AI 에이전트와 멀티에이전트 시스템",
            "source": "demo_fixture",
            "source_type": "technology",
            "title": "AI 에이전트와 멀티에이전트 시스템",
            "url": "https://docs.langchain.com/oss/python/langchain/multi-agent",
            "published_at": now.isoformat(),
            "engagement": 88,
            "raw_score": {"change_type": "demo_new_model"},
            "aliases": ["AI Agent", "Multi-Agent"],
            "official_source_url": "https://docs.langchain.com/oss/python/langgraph/overview",
            "metadata": {"is_demo": True},
        },
        {
            "candidate_id": "demo-hn-agent",
            "topic": "AI 에이전트",
            "source": "demo_fixture_community",
            "source_type": "community",
            "title": "Developers discuss AI agent orchestration",
            "url": "https://news.ycombinator.com/",
            "published_at": now.isoformat(),
            "engagement": 82,
            "raw_score": {"score": 420, "comments": 180},
            "aliases": ["Agentic AI"],
            "official_source_url": None,
            "metadata": {"is_demo": True},
        },
        {
            "candidate_id": "demo-ondevice",
            "topic": "온디바이스 생성형 AI",
            "source": "demo_fixture",
            "source_type": "ecosystem",
            "title": "On-device generative AI repositories",
            "url": "https://github.com/topics/on-device-ai",
            "published_at": (now - timedelta(days=1)).isoformat(),
            "engagement": 76,
            "raw_score": {"stars": 850, "forks": 90},
            "aliases": ["Edge AI"],
            "official_source_url": None,
            "metadata": {"is_demo": True},
        },
    ]


def demo_research(topic: str, attempt: int) -> tuple[list[dict], list[dict]]:
    published = datetime.now(UTC).isoformat()
    sources = [
        {
            "title": "LangGraph overview (demo fixture)",
            "url": "https://docs.langchain.com/oss/python/langgraph/overview",
            "type": "official",
            "publisher": "LangChain",
            "published_at": published,
            "description": "LangGraph is an orchestration framework for controllable agents.",
        },
        {
            "title": "OpenAI Agents guide (demo fixture)",
            "url": "https://platform.openai.com/docs/guides/agents",
            "type": "official",
            "publisher": "OpenAI",
            "published_at": published,
            "description": "Agents combine models, tools, knowledge, and control-flow logic.",
        },
        {
            "title": "Multi-agent systems overview (demo fixture)",
            "url": "https://docs.langchain.com/oss/python/langchain/multi-agent",
            "type": "official",
            "publisher": "LangChain",
            "published_at": published,
            "description": "Multi-agent patterns split complex work across specialized components.",
        },
    ]
    facts = [
        {"claim": "LangGraph는 상태를 공유하는 장기 실행 에이전트 워크플로를 오케스트레이션하는 프레임워크다.", "source_indexes": [0, 2]},
        {"claim": "에이전트 시스템은 모델, 도구, 지식과 제어 흐름을 결합할 수 있다.", "source_indexes": [0, 1]},
        {"claim": "멀티에이전트 구조는 복잡한 작업을 전문 역할별 구성요소로 나눌 수 있다.", "source_indexes": [1, 2]},
    ]
    return sources, facts

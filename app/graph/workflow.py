from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.content_review_agent import ContentReviewAgent
from app.agents.fact_check_agent import FactCheckAgent
from app.agents.finalizer import (
    finalize_content_review_failed,
    finalize_insufficient,
    finalize_rejected,
    finalize_user_rejected,
)
from app.agents.human_approval import human_approval, mark_awaiting_approval
from app.agents.research_agent import ResearchAgent
from app.agents.threads_publisher import ThreadsPublisherAgent
from app.agents.threads_writer import ThreadsWriterAgent
from app.agents.trend_agent import TrendDiscoveryAgent
from app.agents.trend_analyzer import TrendAnalyzerAgent
from app.agents.trend_normalizer import TrendNormalizerAgent
from app.config import Settings, get_settings
from app.graph.routers import route_approval, route_content_review, route_fact_check, route_trend_score
from app.graph.state import TrendThreadsState
from app.tools.trends import GoogleNewsRssTool


def build_graph(settings: Settings | None = None, checkpointer=None):
    """Interrupt 이후 같은 thread_id로 재개할 수 있는 실행 가능한 StateGraph."""
    settings = settings or get_settings()
    google_news = GoogleNewsRssTool(settings.request_timeout_seconds)

    builder = StateGraph(TrendThreadsState)
    builder.add_node("trend_discovery", TrendDiscoveryAgent(settings))
    builder.add_node("trend_normalizer", TrendNormalizerAgent())
    builder.add_node("trend_analysis", TrendAnalyzerAgent())
    builder.add_node("research", ResearchAgent(settings, google_news))
    builder.add_node("fact_check", FactCheckAgent(settings))
    builder.add_node("threads_writer", ThreadsWriterAgent(settings))
    builder.add_node("content_review", ContentReviewAgent())
    builder.add_node("awaiting_approval", mark_awaiting_approval)
    builder.add_node("human_approval", human_approval)
    builder.add_node("threads_publisher", ThreadsPublisherAgent(settings))
    builder.add_node("rejected", finalize_rejected)
    builder.add_node("insufficient", finalize_insufficient)
    builder.add_node("content_review_failed", finalize_content_review_failed)
    builder.add_node("user_rejected", finalize_user_rejected)

    builder.add_edge(START, "trend_discovery")
    builder.add_edge("trend_discovery", "trend_normalizer")
    builder.add_edge("trend_normalizer", "trend_analysis")
    builder.add_conditional_edges("trend_analysis", route_trend_score, {"research": "research", "rejected": "rejected"})
    builder.add_edge("research", "fact_check")
    builder.add_conditional_edges(
        "fact_check",
        route_fact_check,
        {"research": "research", "writer": "threads_writer", "insufficient": "insufficient"},
    )
    builder.add_edge("threads_writer", "content_review")
    builder.add_conditional_edges(
        "content_review",
        route_content_review,
        {"approval": "awaiting_approval", "writer": "threads_writer", "failed": "content_review_failed"},
    )
    builder.add_edge("awaiting_approval", "human_approval")
    builder.add_conditional_edges(
        "human_approval",
        route_approval,
        {"publish": "threads_publisher", "review": "content_review", "reject": "user_rejected"},
    )

    for terminal in ("threads_publisher", "rejected", "insufficient", "content_review_failed", "user_rejected"):
        builder.add_edge(terminal, END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())


graph = build_graph()

from langgraph.types import Command

from app.agents.research_agent import ResearchAgent
from app.config import Settings
from app.graph.state import initial_state
from app.graph.workflow import build_graph
from app.tools.threads_api import ThreadsPublishingTool


def payload(**overrides):
    base = {
        "region": "GLOBAL",
        "language": "ko",
        "category": "AI",
        "period": "14d",
        "min_trend_score": 70,
        "content_style": "informative",
        "auto_publish": False,
        "demo_mode": True,
        "run_id": "graph-test",
    }
    base.update(overrides)
    return base


def config(thread_id="graph-test"):
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 35}


def test_graph_compiles_invokes_and_interrupts_for_approval():
    settings = Settings(openai_api_key=None, threads_access_token=None, threads_user_id=None)
    workflow = build_graph(settings)
    result = workflow.invoke(initial_state(payload(), 2), config())
    assert result["status"] == "awaiting_approval"
    assert result["publish_status"] == "awaiting_approval"
    assert len(result["thread_post"]["full_text"]) <= 500
    assert result["review"]["needs_revision"] is False
    assert result["thread_post"]["hook"].startswith("스친이들~")
    assert workflow.get_state(config()).next == ("human_approval",)


def test_reject_resumes_same_graph_without_publishing():
    settings = Settings(openai_api_key=None, threads_access_token=None, threads_user_id=None)
    workflow = build_graph(settings)
    workflow.invoke(initial_state(payload(run_id="reject-test"), 2), config("reject-test"))
    result = workflow.invoke(Command(resume={"action": "reject"}), config("reject-test"))
    assert result["status"] == "rejected_by_user"
    assert result["publish_status"] == "rejected"
    assert not any(step.startswith("threads_publish") for step in result["execution_trace"])


def test_approve_requires_real_threads_credentials():
    settings = Settings(openai_api_key=None, threads_access_token=None, threads_user_id=None)
    workflow = build_graph(settings)
    workflow.invoke(initial_state(payload(run_id="approve-test"), 2), config("approve-test"))
    result = workflow.invoke(Command(resume={"action": "approve"}), config("approve-test"))
    assert result["status"] == "publish_failed"
    assert result["publish_status"] == "configuration_required"


def test_publish_tool_is_called_only_after_explicit_approval(monkeypatch):
    published_texts = []

    def fake_publish(self, full_text):
        published_texts.append(full_text)
        return {
            "publish_status": "published",
            "threads_post_id": "post-123",
            "threads_permalink": "https://www.threads.com/@tester/post/abc",
        }

    monkeypatch.setattr(ThreadsPublishingTool, "publish_text", fake_publish)
    settings = Settings(openai_api_key=None, threads_access_token="token", threads_user_id="user")
    workflow = build_graph(settings)
    workflow.invoke(initial_state(payload(run_id="publish-test"), 2), config("publish-test"))
    assert published_texts == []

    result = workflow.invoke(Command(resume={"action": "approve"}), config("publish-test"))
    assert result["status"] == "published"
    assert result["threads_post_id"] == "post-123"
    assert published_texts == [result["thread_post"]["full_text"]]


def test_human_edit_is_reviewed_and_interrupts_again():
    workflow = build_graph(Settings(openai_api_key=None))
    first = workflow.invoke(initial_state(payload(run_id="edit-test"), 2), config("edit-test"))
    edited = first["thread_post"]["full_text"].replace("어떻게 보시나요?", "어떤 변화가 중요해 보이나요?")
    second = workflow.invoke(Command(resume={"action": "edit", "edited_text": edited}), config("edit-test"))
    assert second["status"] == "awaiting_approval"
    assert second["thread_post"]["full_text"] == edited
    assert second["review"]["needs_revision"] is False
    assert workflow.get_state(config("edit-test")).next == ("human_approval",)


def test_low_confidence_research_loop_is_bounded(monkeypatch):
    def empty_research(self, state):
        count = state.get("research_retry_count", 0)
        return {"sources": [], "raw_facts": [], "execution_trace": [f"research:forced_empty:retry_{count}"]}

    monkeypatch.setattr(ResearchAgent, "__call__", empty_research)
    workflow = build_graph(Settings(openai_api_key=None, max_research_retry=2))
    result = workflow.invoke(initial_state(payload(run_id="retry-test"), 2), config("retry-test"))
    research_steps = [x for x in result["execution_trace"] if x.startswith("research:")]
    assert len(research_steps) == 3
    assert result["research_retry_count"] == 3
    assert result["status"] == "insufficient_evidence"

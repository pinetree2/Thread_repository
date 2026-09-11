from __future__ import annotations

import re

from langgraph.types import interrupt

from app.graph.state import TrendThreadsState


def mark_awaiting_approval(state: TrendThreadsState) -> dict:
    """Interrupt 직전 상태를 commit해 API가 안전하게 대기 상태를 표시하게 한다."""
    return {
        "status": "awaiting_approval",
        "publish_status": "awaiting_approval",
        "execution_trace": ["human_approval:awaiting"],
    }


def _post_from_edit(text: str) -> dict[str, str]:
    text = text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    hook = lines[0] if lines else text
    ending = lines[-1] if len(lines) > 1 else hook
    body_lines = lines[1:-1]
    body = "\n".join(body_lines) if body_lines else hook
    return {"hook": hook, "body": body, "ending": ending, "full_text": text}


def human_approval(state: TrendThreadsState) -> dict:
    """LangGraph interrupt로 같은 run을 중단하고 사용자의 결정을 기다린다."""
    decision = interrupt(
        {
            "type": "threads_publish_approval",
            "thread_post": state.get("thread_post"),
            "review": state.get("review"),
            "message": "Approve, Edit, Reject 중 하나를 선택하세요.",
        }
    )
    action = str(decision.get("action", "reject"))
    if action == "approve":
        return {
            "approval_decision": "approve",
            "approved": True,
            "publish_status": "publishing",
            "execution_trace": ["human_approval:approved"],
        }
    if action == "edit":
        edited_text = str(decision.get("edited_text", "")).strip()
        hashtags = re.findall(r"(?<!\w)#[\w가-힣]+", edited_text)
        return {
            "approval_decision": "edit",
            "approved": False,
            "thread_post": _post_from_edit(edited_text),
            "hashtags": hashtags or state.get("hashtags", []),
            "review": None,
            "status": "running",
            "publish_status": "not_ready",
            "execution_trace": ["human_approval:edited"],
        }
    return {
        "approval_decision": "reject",
        "approved": False,
        "publish_status": "rejected",
        "execution_trace": ["human_approval:rejected"],
    }

from __future__ import annotations

import json
import hmac
import hashlib
import queue
import threading
import time
from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from app.config import get_settings
from app.graph.state import initial_state
from app.graph.workflow import graph
from app.models import AnalyzeRequest, AnalyzeResponse, ApprovalRequest
from app.services.result_store import LatestResultStore

router = APIRouter(prefix="/api")


def _result_store() -> LatestResultStore:
    return LatestResultStore(get_settings().data_dir)


def _cron_credential(settings) -> str | None:
    """Use an explicit secret when configured; otherwise derive one locally.

    This lets a first deployment work without asking the user to invent another
    secret. The raw Threads token is never returned or logged.
    """
    if settings.cron_secret:
        return settings.cron_secret
    if settings.threads_access_token:
        return hashlib.sha256(settings.threads_access_token.encode()).hexdigest()
    return None


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}, "recursion_limit": 35}


def _response_from_state(state: dict) -> AnalyzeResponse:
    unique_errors = list(
        {(item.get("source", ""), item.get("reason", "")): item for item in state.get("api_errors", [])}.values()
    )
    return AnalyzeResponse.model_validate(
        {
            "run_id": state.get("run_id", ""),
            "topic": state.get("selected_topic", ""),
            "trend_score": state.get("trend_score", 0),
            "trend_reason": state.get("trend_reason", ""),
            "trend_signals": state.get("selected_cluster", {}).get("candidates", []),
            "score_breakdown": state.get("score_breakdown", {}),
            "verified_facts": state.get("verified_facts", []),
            "sources": state.get("sources", []),
            "confidence": state.get("confidence", 0),
            "thread_post": state.get("thread_post"),
            "hashtags": state.get("hashtags", []),
            "review": state.get("review"),
            "publish_status": state.get("publish_status", "not_ready"),
            "threads_post_id": state.get("threads_post_id"),
            "threads_permalink": state.get("threads_permalink"),
            "approved": state.get("approved", False),
            "status": state.get("status", "failed"),
            "data_mode": state.get("data_mode", "live"),
            "region": state.get("region", "GLOBAL"),
            "language": state.get("language", "ko"),
            "content_style": state.get("content_style", "informative"),
            "auto_publish": state.get("auto_publish", False),
            "available_sources": list(dict.fromkeys(state.get("available_sources", []))),
            "successful_sources": list(dict.fromkeys(state.get("successful_sources", []))),
            "api_errors": unique_errors,
            "warnings": state.get("warnings", []),
            "execution_trace": state.get("execution_trace", []),
        }
    )


def _make_initial(request: AnalyzeRequest, run_id: str) -> dict:
    settings = get_settings()
    payload = {**request.model_dump(), "run_id": run_id}
    return initial_state(
        payload,
        settings.max_research_retry,
        settings.fact_check_threshold,
        settings.max_content_retry,
    )


def _saved_state(run_id: str) -> dict:
    snapshot = graph.get_state(_config(run_id))
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="run_id를 찾을 수 없습니다")
    return dict(snapshot.values)


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "project": "Trend2Threads AI",
        "graph_compiled": graph is not None,
        "integrations": {
            "google_rss": True,
            "ai_model_watch": True,
            "hackernews": True,
            "github": True,
            "serpapi_youtube_configured": settings.has_serpapi_credentials,
            "naver_news_configured": settings.has_naver_credentials,
            "openai_configured": settings.has_llm_credentials,
            "threads_publish_configured": settings.has_threads_credentials,
        },
    }


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    run_id = uuid4().hex
    state = await run_in_threadpool(graph.invoke, _make_initial(request, run_id), _config(run_id))
    return _response_from_state(state)


@router.post("/scheduled/analyze", response_model=AnalyzeResponse)
async def scheduled_analyze(
    request: AnalyzeRequest,
    x_cron_secret: str | None = Header(default=None),
) -> AnalyzeResponse:
    """Cloudflare Cron entry point. It creates a draft but never bypasses approval."""
    settings = get_settings()
    expected_cron = _cron_credential(settings)
    if not expected_cron or not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected_cron):
        raise HTTPException(status_code=401, detail="invalid cron credential")
    safe_request = request.model_copy(update={"auto_publish": False})
    run_id = uuid4().hex
    state = await run_in_threadpool(graph.invoke, _make_initial(safe_request, run_id), _config(run_id))
    response = _response_from_state(state)
    _result_store().save(response.model_dump(mode="json"))
    return response


@router.get("/latest", response_model=AnalyzeResponse)
def latest_result() -> AnalyzeResponse:
    payload = _result_store().load()
    if payload is None:
        raise HTTPException(status_code=404, detail="아직 저장된 정기 분석 결과가 없습니다")
    return AnalyzeResponse.model_validate(payload)


@router.post("/analyze/stream")
def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    run_id = uuid4().hex

    def generate() -> Iterator[str]:
        latest = _make_initial(request, run_id)
        yield json.dumps({"event": "run", "run_id": run_id}, ensure_ascii=False) + "\n"
        event_queue: queue.Queue[dict] = queue.Queue()

        def run_graph() -> None:
            current = latest
            previous_trace_length = 0
            try:
                for snapshot in graph.stream(current, _config(run_id), stream_mode="values"):
                    current = snapshot
                    trace = current.get("execution_trace", [])
                    if len(trace) > previous_trace_length:
                        event_queue.put({
                            "event": "progress",
                            "step": trace[-1],
                            "trace": trace,
                            "run_id": run_id,
                        })
                        previous_trace_length = len(trace)
                event_queue.put({
                    "event": "complete",
                    "result": _response_from_state(current).model_dump(mode="json"),
                })
            except Exception as exc:
                event_queue.put({"event": "error", "message": str(exc), "run_id": run_id})

        started_at = time.monotonic()
        worker = threading.Thread(target=run_graph, name=f"analysis-{run_id[:8]}", daemon=True)
        worker.start()
        yield json.dumps(
            {"event": "activity", "message": "외부 트렌드 소스 수집을 시작했습니다.", "elapsed": 0},
            ensure_ascii=False,
        ) + "\n"

        while True:
            try:
                event = event_queue.get(timeout=2.0)
            except queue.Empty:
                elapsed = int(time.monotonic() - started_at)
                yield json.dumps(
                    {"event": "heartbeat", "message": "Agent가 현재 단계를 처리 중입니다.", "elapsed": elapsed},
                    ensure_ascii=False,
                ) + "\n"
                continue
            yield json.dumps(event, ensure_ascii=False) + "\n"
            if event["event"] in {"complete", "error"}:
                break

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}", response_model=AnalyzeResponse)
def get_run(run_id: str) -> AnalyzeResponse:
    return _response_from_state(_saved_state(run_id))


@router.post("/runs/{run_id}/decision", response_model=AnalyzeResponse)
async def decide(run_id: str, request: ApprovalRequest) -> AnalyzeResponse:
    snapshot = graph.get_state(_config(run_id))
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="run_id를 찾을 수 없습니다")
    if "human_approval" not in snapshot.next:
        raise HTTPException(status_code=409, detail="현재 실행은 승인 대기 상태가 아닙니다")
    state = await run_in_threadpool(
        graph.invoke,
        Command(resume=request.model_dump(exclude_none=True)),
        _config(run_id),
    )
    return _response_from_state(state)


@router.get("/graph")
def graph_diagram() -> dict:
    return {"mermaid": graph.get_graph().draw_mermaid()}

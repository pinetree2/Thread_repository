from __future__ import annotations

import argparse
import json
import sys
from uuid import uuid4

from app.api.routes import _response_from_state
from app.config import get_settings
from app.graph.state import initial_state
from app.graph.workflow import graph
from app.models import AnalyzeRequest


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run Trend2Threads AI from the command line")
    parser.add_argument("--region", default="GLOBAL")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--category", default="AI")
    parser.add_argument("--period", default="14d")
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument(
        "--style",
        choices=("threads_casual", "informative", "conversational", "insightful"),
        default="threads_casual",
    )
    parser.add_argument("--demo", action="store_true", help="Use clearly-labelled local fixtures")
    args = parser.parse_args()
    request = AnalyzeRequest(
        region=args.region,
        language=args.language,
        category=args.category,
        period=args.period,
        min_trend_score=args.min_score,
        content_style=args.style,
        auto_publish=False,
        demo_mode=args.demo,
    )
    settings = get_settings()
    run_id = uuid4().hex
    state = initial_state(
        {**request.model_dump(), "run_id": run_id},
        settings.max_research_retry,
        settings.fact_check_threshold,
        settings.max_content_retry,
    )
    result = graph.invoke(state, {"configurable": {"thread_id": run_id}, "recursion_limit": 35})
    print(json.dumps(_response_from_state(result).model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

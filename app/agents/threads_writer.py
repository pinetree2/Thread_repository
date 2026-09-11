from __future__ import annotations

import json
import re

from openai import OpenAI

from app.config import Settings
from app.graph.state import TrendThreadsState
from app.models import ThreadsPackage
from app.prompts.content import THREADS_SYSTEM_PROMPT, build_threads_prompt


THREADS_TEXT_LIMIT = 500


def _compact(text: str) -> str:
    return " ".join(text.split()).strip()


def _trim(text: str, limit: int) -> str:
    text = "\n".join(_compact(line) for line in text.splitlines() if _compact(line))
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)].rstrip(" ,.;:!?。") + "..."


def _fallback_package(
    topic: str,
    facts: list[str],
    sources: list[dict],
    language: str,
    style: str,
) -> ThreadsPackage:
    if language == "ko":
        if style in {"threads_casual", "informative", "conversational"}:
            hook = f"스친이들~ 오늘은 {topic} 얘기해봄."
        else:
            hook = f"지금 주목할 글로벌 AI 흐름은 {topic}입니다."
        ending = "과장 말고 근거로 봐야 할 듯. 스친들은 이 변화 어떻게 봄?"
        hashtags = ["#AI", "#테크", "#AI트렌드"]
    else:
        hook = f'The global AI trend worth watching now is "{topic}."'
        ending = "Evidence matters more than hype. What is your take?"
        hashtags = ["#AI", "#Tech", "#AITrends"]

    if style == "conversational":
        ending = "스친들은 어떻게 생각함?" if language == "ko" else "What do you think?"
    elif style == "insightful":
        ending = "이 변화가 실제 채택으로 이어질지 지켜볼 필요가 있습니다." if language == "ko" else "It is worth watching whether this turns into real adoption."

    fact_text = [_compact(fact) for fact in facts[:3] if _compact(fact)]
    if fact_text:
        body = "\n".join(f"- {fact}" for fact in fact_text)
    else:
        body = "검증 가능한 근거가 더 필요합니다." if language == "ko" else "More verifiable evidence is required."

    source_names = list(dict.fromkeys(
        str(source.get("publisher") or source.get("title") or "").strip()
        for source in sources[:4]
        if str(source.get("publisher") or source.get("title") or "").strip()
    ))[:2]
    if source_names:
        body += "\n출처: " + " · ".join(source_names)
    tags = " ".join(hashtags)
    fixed_length = len(hook) + len(ending) + len(tags) + 6
    body = _trim(body, max(40, THREADS_TEXT_LIMIT - fixed_length))
    full_text = f"{hook}\n\n{body}\n\n{ending}\n\n{tags}"
    return ThreadsPackage.model_validate(
        {"thread_post": {"hook": hook, "body": body, "ending": ending, "full_text": full_text}, "hashtags": hashtags}
    )


def numbers_are_grounded(package: ThreadsPackage, evidence: list[str]) -> bool:
    allowed = set(re.findall(r"\d+(?:[.,]\d+)?", " ".join(evidence)))
    generated = set(re.findall(r"\d+(?:[.,]\d+)?", package.thread_post.full_text))
    # '세 가지'의 의미로 쓰는 1~9 같은 단일 구조 숫자는 허용하되,
    # 날짜·버전·비율·성능처럼 사실 주장이 되는 다자리/소수 숫자는 근거와 대조한다.
    factual_numbers = {value for value in generated if len(value) > 1 or "." in value or "," in value}
    return factual_numbers <= allowed


class ThreadsWriterAgent:
    """검증된 사실만으로 게시 가능한 500자 이하 Threads 글을 작성한다."""

    name = "Threads Writer Agent"
    allowed_tools = ("OpenAI Responses API (optional)", "grounded deterministic writer")

    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self, state: TrendThreadsState) -> dict:
        topic = state["selected_topic"]
        facts = state.get("verified_facts", [])
        sources = state.get("sources", [])
        language = state.get("language", "ko")
        style = state.get("content_style", "informative")
        package = _fallback_package(topic, facts, sources, language, style)
        warnings: list[str] = []
        trace = "threads_writer:deterministic_grounded"

        if self.settings.has_llm_credentials and facts:
            try:
                client = OpenAI(api_key=self.settings.openai_api_key)
                source_context = [
                    {
                        "title": source.get("title", ""),
                        "publisher": source.get("publisher", ""),
                        "type": source.get("type", ""),
                        "url": str(source.get("url", "")),
                    }
                    for source in sources[:6]
                ]
                prompt = build_threads_prompt(topic, facts, source_context, language, style)
                response = client.responses.create(
                    model=self.settings.openai_model,
                    input=[
                        {"role": "system", "content": THREADS_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    text={"format": {"type": "json_schema", "name": "trend2threads_post", "strict": True,
                                     "schema": ThreadsPackage.model_json_schema()}},
                )
                payload = json.loads(response.output_text)
                post = payload.get("thread_post", {})
                hashtags = [str(tag).strip() for tag in payload.get("hashtags", []) if str(tag).strip()][:4]
                hook = _compact(str(post.get("hook", "")))
                body = str(post.get("body", "")).strip()
                ending = _compact(str(post.get("ending", "")))
                tags = " ".join(hashtags)
                fixed_length = len(hook) + len(ending) + len(tags) + 6
                body = _trim(body, max(40, THREADS_TEXT_LIMIT - fixed_length))
                # 모델의 full_text 복제 편차를 신뢰하지 않고 검증된 섹션으로
                # 게시 가능한 최종 문자열을 결정론적으로 재조립한다.
                full_text = f"{hook}\n\n{body}\n\n{ending}\n\n{tags}"
                candidate = ThreadsPackage.model_validate(
                    {
                        "thread_post": {
                            "hook": hook,
                            "body": body,
                            "ending": ending,
                            "full_text": full_text,
                        },
                        "hashtags": hashtags,
                    }
                )
                evidence = [topic, *facts]
                evidence.extend(
                    f"{source.get('title', '')} {source.get('publisher', '')} {source.get('published_at', '')}"
                    for source in sources
                )
                if not numbers_are_grounded(candidate, evidence):
                    raise ValueError("검증 사실에 없는 숫자가 생성되었습니다")
                package = candidate
                trace = f"threads_writer:openai:{self.settings.openai_model}"
            except Exception as exc:
                warnings.append(f"LLM 작성 실패로 근거 기반 규칙 작성기를 사용했습니다: {exc}")
        elif not self.settings.has_llm_credentials:
            warnings.append("OPENAI_API_KEY 미설정: 검증 사실 기반 규칙 작성기를 사용했습니다.")

        return {
            **package.model_dump(),
            "review": None,
            "warnings": warnings,
            "execution_trace": [trace],
        }

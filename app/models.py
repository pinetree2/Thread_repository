from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class AnalyzeRequest(BaseModel):
    region: str = Field(default="GLOBAL", pattern=r"^(GLOBAL|[A-Za-z]{2})$")
    language: str = Field(default="ko", pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    category: str = Field(default="AI", min_length=1, max_length=80)
    period: str = Field(default="14d", pattern=r"^\d+[dhw]$")
    min_trend_score: int = Field(default=0, ge=0, le=100)
    content_style: Literal["threads_casual", "informative", "conversational", "insightful"] = "threads_casual"
    # 안전 원칙: 이 값이 true여도 Human Approval을 우회하지 않는다.
    auto_publish: bool = False
    demo_mode: bool = False

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        return value.upper()


class TrendCandidate(BaseModel):
    candidate_id: str
    topic: str
    source: str
    source_type: Literal["technology", "community", "video", "ecosystem", "search"]
    title: str
    url: HttpUrl
    published_at: datetime
    engagement: float = Field(ge=0, le=100)
    raw_score: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    official_source_url: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    title: str
    url: HttpUrl
    type: Literal["official", "news", "research", "community", "demo"] = "news"
    publisher: str = ""
    published_at: str | None = None
    description: str = ""


class ThreadPost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hook: str = Field(min_length=1)
    body: str = Field(min_length=1)
    ending: str = Field(min_length=1)
    full_text: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def full_text_contains_sections(self) -> "ThreadPost":
        if not all(part.strip() in self.full_text for part in (self.hook, self.body, self.ending)):
            raise ValueError("full_text에는 hook, body, ending이 모두 포함되어야 합니다")
        return self


class ThreadsPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_post: ThreadPost
    hashtags: list[str] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def hashtags_are_in_full_text(self) -> "ThreadsPackage":
        if not all(tag.startswith("#") and tag in self.thread_post.full_text for tag in self.hashtags):
            raise ValueError("모든 hashtag는 #으로 시작하고 full_text에 포함되어야 합니다")
        return self


class ContentReview(BaseModel):
    factually_grounded: bool
    source_supported: bool
    quality_score: float = Field(ge=0, le=1)
    needs_revision: bool
    issues: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def edit_requires_text(self) -> "ApprovalRequest":
        if self.action == "edit" and not (self.edited_text or "").strip():
            raise ValueError("edit 작업에는 edited_text가 필요합니다")
        return self


class AnalyzeResponse(BaseModel):
    run_id: str
    topic: str
    trend_score: float = Field(ge=0, le=100)
    trend_reason: str
    trend_signals: list[TrendCandidate] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    verified_facts: list[str]
    sources: list[Source]
    confidence: float = Field(ge=0, le=1)
    thread_post: ThreadPost | None = None
    hashtags: list[str] = Field(default_factory=list)
    review: ContentReview | None = None
    publish_status: Literal[
        "not_ready",
        "awaiting_approval",
        "publishing",
        "published",
        "rejected",
        "configuration_required",
        "failed",
    ] = "not_ready"
    threads_post_id: str | None = None
    threads_permalink: HttpUrl | None = None
    approved: bool = False
    status: Literal[
        "awaiting_approval",
        "published",
        "publish_failed",
        "rejected_by_user",
        "content_review_failed",
        "no_qualified_trend",
        "insufficient_evidence",
        "failed",
    ]
    data_mode: Literal["live", "demo"]
    region: str
    language: str
    content_style: str
    auto_publish: bool
    available_sources: list[str] = Field(default_factory=list)
    successful_sources: list[str] = Field(default_factory=list)
    api_errors: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    execution_trace: list[str] = Field(default_factory=list)

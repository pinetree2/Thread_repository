import pytest
from pydantic import ValidationError

from app.models import AnalyzeRequest, ApprovalRequest, ThreadPost


def test_request_defaults_and_normalization():
    request = AnalyzeRequest(region="kr", language="ko")
    assert request.region == "KR"
    assert request.period == "14d"
    assert request.content_style == "threads_casual"
    assert request.auto_publish is False
    assert not hasattr(request, "video_duration")


def test_request_rejects_bad_period():
    with pytest.raises(ValidationError):
        AnalyzeRequest(period="two weeks")


def test_thread_post_enforces_publishable_full_text():
    with pytest.raises(ValidationError):
        ThreadPost(hook="h", body="b", ending="e", full_text="x" * 501)
    with pytest.raises(ValidationError):
        ThreadPost(hook="hook", body="body", ending="ending", full_text="hook only")


def test_edit_decision_requires_text():
    with pytest.raises(ValidationError):
        ApprovalRequest(action="edit")

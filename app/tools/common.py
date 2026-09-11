from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime


class ExternalToolError(RuntimeError):
    """Raised when an external provider cannot return usable data."""


def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value or ""))).strip()


def parse_published(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)


def period_to_days(period: str) -> int:
    amount, unit = int(period[:-1]), period[-1]
    if unit == "h":
        return max(1, (amount + 23) // 24)
    if unit == "w":
        return amount * 7
    return amount


def inside_period(published_at: str | None, period: str) -> bool:
    cutoff = datetime.now(UTC) - timedelta(days=period_to_days(period))
    return parse_published(published_at) >= cutoff


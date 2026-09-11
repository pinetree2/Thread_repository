from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import httpx

from app.models import TrendCandidate
from app.tools.common import ExternalToolError, period_to_days
from app.tools.topic_normalization import canonical_topic


class AIModelWatchTool:
    """Detects new model/lifecycle events from the public AI Model Watch API."""

    models_endpoint = "https://aimodelwatch.dev/api/models.json"
    deprecations_endpoint = "https://aimodelwatch.dev/api/deprecations.json"

    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    def _fetch(self, url: str) -> dict:
        try:
            response = httpx.get(
                url,
                headers={"Accept": "application/json", "User-Agent": "Trend2Threads-AI/2.0"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalToolError(f"AI Model Watch 요청 실패: {exc}") from exc

    def collect(self, period: str) -> list[TrendCandidate]:
        cutoff = datetime.now(UTC) - timedelta(days=period_to_days(period))
        models_payload = self._fetch(self.models_endpoint)
        deprecations_payload = self._fetch(self.deprecations_endpoint)
        candidates: list[TrendCandidate] = []
        seen: set[str] = set()

        for change_type, payload, date_field in (
            ("new_model", models_payload, "released"),
            ("deprecation", deprecations_payload, "deprecated_on"),
        ):
            for model in payload.get("models", []):
                date_value = model.get(date_field)
                if not date_value:
                    continue
                try:
                    published = datetime.fromisoformat(str(date_value)).replace(tzinfo=UTC)
                except ValueError:
                    continue
                unique = f"{change_type}:{model.get('id') or model.get('api_string') or model.get('name')}"
                if published < cutoff or unique in seen:
                    continue
                seen.add(unique)
                name = model.get("name") or model.get("api_string") or "Unknown model"
                provider = model.get("provider") or "Unknown provider"
                official_url = model.get("source_url") or "https://aimodelwatch.dev"
                freshness = max(0.0, 1 - (datetime.now(UTC) - published).days / max(period_to_days(period), 1))
                engagement = min(100.0, 72 + freshness * 20 + (8 if change_type == "new_model" else 3))
                title = f"{provider} {name} {'released' if change_type == 'new_model' else 'deprecated'}"
                candidates.append(
                    TrendCandidate(
                        candidate_id=f"modelwatch:{unique}",
                        topic=canonical_topic(name),
                        source="ai_model_watch",
                        source_type="technology",
                        title=title,
                        url=official_url,
                        published_at=published,
                        engagement=round(engagement, 1),
                        raw_score={
                            "change_type": change_type,
                            "provider": provider,
                            "status": model.get("status"),
                            "released": model.get("released"),
                            "deprecated_on": model.get("deprecated_on"),
                            "retires_on": model.get("retires_on"),
                            "replacement": model.get("replacement"),
                        },
                        aliases=[name, model.get("api_string") or name],
                        official_source_url=official_url,
                        metadata={"catalog_updated": payload.get("updated")},
                    )
                )
        return candidates

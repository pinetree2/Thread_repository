from __future__ import annotations

from app.graph.state import TrendThreadsState
from app.models import TrendCandidate
from app.tools.topic_normalization import canonical_topic, topic_similarity


class TrendNormalizerAgent:
    """Validates provider payloads and clusters equivalent topic names."""

    name = "Trend Normalizer / Topic Clustering Agent"
    allowed_tools = ("TrendCandidate Pydantic schema", "keyword canonicalizer", "string similarity")

    def __call__(self, state: TrendThreadsState) -> dict:
        valid: list[dict] = []
        api_errors: list[dict[str, str]] = []
        for raw in state.get("trend_candidates", []):
            try:
                valid.append(TrendCandidate.model_validate(raw).model_dump(mode="json"))
            except Exception as exc:
                api_errors.append({"source": raw.get("source", "unknown"), "reason": f"normalization failed: {exc}"})

        clusters: list[dict] = []
        for candidate in sorted(valid, key=lambda item: item["engagement"], reverse=True):
            canonical = canonical_topic(candidate["topic"] or candidate["title"])
            target = next(
                (cluster for cluster in clusters if topic_similarity(cluster["topic"], canonical) >= 0.72),
                None,
            )
            if target is None:
                target = {"topic": canonical, "aliases": [], "candidates": [], "sources": [], "source_types": []}
                clusters.append(target)
            target["candidates"].append(candidate)
            target["aliases"] = sorted(set(target["aliases"] + candidate.get("aliases", []) + [candidate["title"]]))
            target["sources"] = sorted(set(target["sources"] + [candidate["source"]]))
            target["source_types"] = sorted(set(target["source_types"] + [candidate["source_type"]]))

        return {
            "normalized_candidates": valid,
            "trend_clusters": clusters,
            "api_errors": api_errors,
            "execution_trace": [f"trend_normalizer:{len(valid)}_valid:{len(clusters)}_clusters"],
        }

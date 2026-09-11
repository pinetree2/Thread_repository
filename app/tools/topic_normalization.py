from __future__ import annotations

import re
from difflib import SequenceMatcher


ENTITY_PATTERNS = [
    (r"\bclaude(?:\s+opus|\s+sonnet|\s+haiku)?(?:\s+\d+(?:\.\d+)?)?\b", "Claude"),
    (r"\bgpt[-\s]?\d+(?:\.\d+)?\b", "GPT"),
    (r"\bgemini(?:\s+\d+(?:\.\d+)?)?\b", "Gemini"),
    (r"\bllama(?:\s+\d+(?:\.\d+)?)?\b", "Llama"),
    (r"\bdeepseek(?:[-\s][a-z0-9.]+)?\b", "DeepSeek"),
    (r"\bqwen(?:[-\s][a-z0-9.]+)?\b", "Qwen"),
    (r"\bmistral(?:[-\s][a-z0-9.]+)?\b", "Mistral"),
    (r"\bmodel context protocol\b|\bmcp\b", "Model Context Protocol (MCP)"),
    (r"\bagentic\s+ai\b|\bai\s+agents?\b|AI\s*에이전트", "AI Agents"),
    (r"\bretrieval augmented generation\b|\brag\b", "RAG"),
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "new", "launch", "launches",
    "released", "release", "introducing", "model", "models", "ai", "open", "source",
    "show", "ask", "github", "repository", "official",
}


def canonical_topic(text: str) -> str:
    clean = re.sub(r"https?://\S+", " ", text).strip()
    for pattern, label in ENTITY_PATTERNS:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            matched = re.sub(r"\s+", " ", match.group(0)).strip()
            if label in {"GPT", "Claude", "Gemini", "Llama", "DeepSeek", "Qwen", "Mistral"}:
                return matched.title().replace("Gpt", "GPT")
            return label
    tokens = [
        token for token in re.findall(r"[A-Za-z0-9가-힣.+-]{2,}", clean)
        if token.lower() not in STOPWORDS
    ]
    return " ".join(tokens[:5]) or clean[:80] or "Unknown AI Topic"


def topic_similarity(left: str, right: str) -> float:
    left_norm = canonical_topic(left).lower()
    right_norm = canonical_topic(right).lower()
    if left_norm == right_norm:
        return 1.0
    left_tokens, right_tokens = set(left_norm.split()), set(right_norm.split())
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    return max(jaccard, sequence)


from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LatestResultStore:
    """Small file-backed store suitable for a mounted Railway volume."""

    def __init__(self, data_dir: str):
        self.directory = Path(data_dir)
        self.path = self.directory / "latest.json"

    def save(self, result: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.directory / "latest.tmp"
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

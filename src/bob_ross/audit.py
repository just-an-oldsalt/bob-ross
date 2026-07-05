"""Append-only JSONL audit log. Every action Bob Ross takes is recorded here.

Secrets are redacted before writing. The log is the source of truth for
"what did the agent do to my fleet" — treat it as sensitive (it's gitignored).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Keys whose values must never be written to the log.
_REDACT = {
    "token",
    "api_token",
    "secret",
    "secret_key",
    "access_key",
    "password",
    "authorization",
    "signature",
}


def redact(value: Any) -> Any:
    """Recursively replace secret-looking values with '***'."""
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _REDACT else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class AuditLog:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def record(
        self,
        *,
        tool: str,
        outcome: str,
        params: dict | None = None,
        target_count: int | None = None,
        detail: Any = None,
    ) -> dict:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "outcome": outcome,  # e.g. read | dry_run | executed | denied | error
            "target_count": target_count,
            "params": redact(params or {}),
            "detail": redact(detail) if detail is not None else None,
        }
        # Append; create parent dir if needed.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
        return entry

"""The safety layer — the reason Bob Ross is better than a dumb API wrapper.

An LLM driving a fleet must never reboot 500 machines by accident. So every
destructive action is a two-step dance:

  1. Dry run  -> returns the *blast radius* (how many machines, a sample) and a
                 short-lived confirm token bound to that exact action + target set.
  2. Confirm  -> the same tool, called again WITH the token, actually executes.

If the target set drifts between the two calls (a machine registered/deregistered),
the token's hash no longer matches and we force a fresh dry run. No stale blasts.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from .config import Settings


class SafetyError(Exception):
    """Raised when a guard rejects an action. The message is agent-facing."""


def _hash_targets(action: str, target_ids: list) -> str:
    canon = action + "|" + ",".join(sorted(str(t) for t in target_ids))
    return hashlib.sha256(canon.encode()).hexdigest()


def ensure_writes_enabled(settings: Settings) -> None:
    if not settings.writes_enabled:
        raise SafetyError(
            "Bob Ross is in read-only mode — no changes will be made. "
            "To enable actions, set BOBROSS_READ_ONLY=false and "
            "BOBROSS_ALLOW_WRITES=true, then restart the server."
        )


@dataclass
class PendingAction:
    token: str
    action: str
    target_hash: str
    target_count: int
    summary: str
    expires_at: float


class ConfirmStore:
    """In-memory store of issued (but not yet consumed) confirm tokens."""

    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self._pending: dict[str, PendingAction] = {}

    def issue(self, action: str, target_ids: list, summary: str) -> PendingAction:
        token = "brush-" + secrets.token_hex(8)
        pending = PendingAction(
            token=token,
            action=action,
            target_hash=_hash_targets(action, target_ids),
            target_count=len(target_ids),
            summary=summary,
            expires_at=time.time() + self.ttl,
        )
        self._pending[token] = pending
        return pending

    def consume(self, token: str, action: str, target_ids: list) -> PendingAction:
        pending = self._pending.get(token)
        if pending is None:
            raise SafetyError(
                "Unknown or already-used confirm token. Re-run the tool without "
                "a token to get a fresh dry run."
            )
        # Single-use: remove now regardless of outcome.
        del self._pending[token]

        if time.time() > pending.expires_at:
            raise SafetyError("Confirm token expired. Re-run the tool for a fresh dry run.")
        if pending.action != action:
            raise SafetyError("Confirm token was issued for a different action.")
        if pending.target_hash != _hash_targets(action, target_ids):
            raise SafetyError(
                "The set of matched machines changed since the dry run. "
                "Re-run without a token to review the new blast radius."
            )
        return pending

    def purge_expired(self) -> None:
        now = time.time()
        for tok in [t for t, p in self._pending.items() if p.expires_at < now]:
            del self._pending[tok]

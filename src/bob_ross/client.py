"""Async Landscape API client supporting both auth backends.

* REST   — ``Authorization: Bearer <token>`` against ``/api/v2/...`` (self-hosted 24.04+).
* Legacy — AWS-SigV2-style HMAC-SHA256 query API against ``/api/`` (SaaS + older).

Endpoint paths/actions live as module constants so they're trivial to adjust
once we point Bob Ross at a real instance (see ``ping`` to validate wiring).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from .config import AuthMode, Settings

LEGACY_API_VERSION = "2011-08-01"
REST_PREFIX = "/api/v2"
LEGACY_PATH = "/api/"

# Activity statuses that mean the job is finished (used by wait_for_activity).
TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "cancelled"}


class LandscapeError(Exception):
    """Raised on a non-2xx response or transport failure. Agent-facing message."""


def sign_query(
    access_key: str,
    secret_key: str,
    url: str,
    action: str,
    params: dict[str, Any],
    *,
    timestamp: str,
) -> dict[str, str]:
    """Return the fully-signed parameter dict for a legacy query-API request.

    Pure function (timestamp injected) so it can be unit-tested deterministically.
    """
    signed: dict[str, str] = {
        "action": action,
        "access_key_id": access_key,
        "signature_version": "2",
        "signature_method": "HmacSHA256",
        "timestamp": timestamp,
        "version": LEGACY_API_VERSION,
    }
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            signed[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value, start=1):
                signed[f"{key}.{i}"] = str(item)
        else:
            signed[key] = str(value)

    # RFC3986 encode, sort by encoded key, build canonical query string.
    encoded = sorted((quote(k, safe=""), quote(v, safe="")) for k, v in signed.items())
    canonical = "&".join(f"{k}={v}" for k, v in encoded)

    host = urlsplit(url).netloc.lower()
    string_to_sign = "\n".join(["POST", host, LEGACY_PATH, canonical])
    digest = hmac.new(secret_key.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    signed["signature"] = base64.b64encode(digest).decode()
    return signed


def encode_body(signed: dict[str, str]) -> str:
    """Serialise signed params into an x-www-form-urlencoded body.

    Built explicitly (not via a dict encoder) so the bytes on the wire match
    exactly what was signed — the server re-derives the signature from the
    decoded params, so any encoding drift causes SignatureDoesNotMatch.
    """
    items = sorted((k, v) for k, v in signed.items() if k != "signature")
    body = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in items)
    return body + "&signature=" + quote(signed["signature"], safe="")


def _as_list(payload: Any) -> list[dict]:
    """Normalise a Landscape response into a list of dicts across API shapes."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("results", "computers", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    return []


class LandscapeClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._http = httpx.AsyncClient(
            verify=settings.tls_verify,
            timeout=settings.request_timeout,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ── transport ───────────────────────────────────────────────────
    async def _rest(self, method: str, path: str, **kw) -> Any:
        url = self.s.landscape_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {self.s.api_token}"}
        return await self._send(self._http.request(method, url, headers=headers, **kw))

    async def _legacy(self, action: str, **params) -> Any:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        signed = sign_query(
            self.s.access_key, self.s.secret_key, self.s.landscape_url, action, params, timestamp=ts
        )
        url = self.s.landscape_url.rstrip("/") + LEGACY_PATH
        return await self._send(
            self._http.post(
                url,
                content=encode_body(signed),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        )

    async def _send(self, coro) -> Any:
        try:
            resp = await coro
        except httpx.HTTPError as exc:  # transport/TLS/timeout
            raise LandscapeError(f"Could not reach Landscape: {exc}") from exc
        if resp.status_code >= 400:
            # Surface the server's error but never echo request auth material.
            body = resp.text[:500]
            raise LandscapeError(f"Landscape returned {resp.status_code}: {body}")
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    @property
    def is_rest(self) -> bool:
        return self.s.auth_mode == AuthMode.rest

    # ── high-level operations ───────────────────────────────────────
    async def ping(self) -> dict:
        """Lightweight connectivity + auth check used by the `ping` tool."""
        computers = await self.get_computers(query="", limit=1)
        return {
            "reachable": True,
            "auth_mode": self.s.auth_mode.value,
            "sample_size": len(computers),
        }

    async def get_computers(self, query: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
        if self.is_rest:
            params = {"limit": limit, "offset": offset}
            if query:
                params["query"] = query
            return _as_list(await self._rest("GET", f"{REST_PREFIX}/computers", params=params))
        # Legacy GetComputers rejects an empty `query` ("MissingParameter") but is
        # happy with it omitted (returns all). Only send it when non-empty.
        kwargs = {"limit": limit, "offset": offset}
        if query:
            kwargs["query"] = query
        return _as_list(await self._legacy("GetComputers", **kwargs))

    async def get_computer(self, computer_id: int) -> dict:
        if self.is_rest:
            return await self._rest("GET", f"{REST_PREFIX}/computers/{computer_id}")
        rows = _as_list(await self._legacy("GetComputers", query=f"id:{computer_id}"))
        if not rows:
            raise LandscapeError(f"No computer with id {computer_id}")
        return rows[0]

    async def get_alerts(self) -> list[dict]:
        if self.is_rest:
            return _as_list(await self._rest("GET", f"{REST_PREFIX}/alerts"))
        return _as_list(await self._legacy("GetAlerts"))

    async def get_activities(self, query: str = "", limit: int = 50) -> list[dict]:
        if self.is_rest:
            params = {"limit": limit}
            if query:
                params["query"] = query
            return _as_list(await self._rest("GET", f"{REST_PREFIX}/activities", params=params))
        kwargs = {"limit": limit}
        if query:
            kwargs["query"] = query
        return _as_list(await self._legacy("GetActivities", **kwargs))

    async def get_activity(self, activity_id: int) -> dict:
        if self.is_rest:
            return await self._rest("GET", f"{REST_PREFIX}/activities/{activity_id}")
        rows = _as_list(await self._legacy("GetActivities", query=f"id:{activity_id}"))
        if not rows:
            raise LandscapeError(f"No activity with id {activity_id}")
        return rows[0]

    async def wait_for_activity(
        self, activity_id: int, timeout: float = 120.0, interval: float = 3.0
    ) -> dict:
        """Poll an activity until it reaches a terminal status or times out."""
        import asyncio
        import time as _time

        deadline = _time.monotonic() + timeout
        last: dict = {}
        while True:
            last = await self.get_activity(activity_id)
            status = (last.get("activity_status") or "").lower()
            if status in TERMINAL_STATUSES:
                return {
                    "activity_id": activity_id,
                    "status": status,
                    "timed_out": False,
                    "summary": last.get("summary"),
                    "result_text": last.get("result_text"),
                }
            if _time.monotonic() >= deadline:
                return {
                    "activity_id": activity_id,
                    "status": status or "unknown",
                    "timed_out": True,
                    "summary": last.get("summary"),
                }
            await asyncio.sleep(interval)

    async def get_packages(
        self,
        query: str,
        *,
        upgrade: bool | None = None,
        installed: bool | None = None,
        available: bool | None = None,
        held: bool | None = None,
        search: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        filters = {
            "upgrade": upgrade,
            "installed": installed,
            "available": available,
            "held": held,
            "search": search,
        }
        if self.is_rest:
            params: dict[str, Any] = {"limit": limit}
            if query:
                params["query"] = query
            params.update({k: v for k, v in filters.items() if v is not None})
            return _as_list(await self._rest("GET", f"{REST_PREFIX}/packages", params=params))
        kwargs: dict[str, Any] = {"query": query, "limit": limit}
        kwargs.update({k: v for k, v in filters.items() if v is not None})
        return _as_list(await self._legacy("GetPackages", **kwargs))

    async def get_scripts(self) -> list[dict]:
        if self.is_rest:
            return _as_list(await self._rest("GET", f"{REST_PREFIX}/scripts"))
        return _as_list(await self._legacy("GetScripts"))

    # ── write operations (only reached through the safety layer) ────
    async def execute_script(self, query: str, script_id: int, username: str) -> dict:
        if self.is_rest:
            body = {"query": query, "script_id": script_id, "username": username}
            return await self._rest("POST", f"{REST_PREFIX}/scripts/{script_id}/execute", json=body)
        return await self._legacy(
            "ExecuteScript", query=query, script_id=script_id, username=username
        )

    async def reboot_computers(self, computer_ids: list[int]) -> dict:
        # NB: legacy RebootComputers takes computer_ids, NOT a query string.
        if self.is_rest:
            return await self._rest(
                "POST", f"{REST_PREFIX}/computers/reboot", json={"computer_ids": computer_ids}
            )
        return await self._legacy("RebootComputers", computer_ids=computer_ids)

    async def add_tags(self, query: str, tags: list[str]) -> dict:
        if self.is_rest:
            return await self._rest(
                "POST", f"{REST_PREFIX}/computers/tags", json={"query": query, "tags": tags}
            )
        return await self._legacy("AddTagsToComputers", query=query, tags=tags)

    async def remove_tags(self, query: str, tags: list[str]) -> dict:
        if self.is_rest:
            return await self._rest(
                "DELETE", f"{REST_PREFIX}/computers/tags", json={"query": query, "tags": tags}
            )
        return await self._legacy("RemoveTagsFromComputers", query=query, tags=tags)

    async def install_packages(self, query: str, packages: list[str]) -> dict:
        if self.is_rest:
            body = {"query": query, "packages": packages}
            return await self._rest("POST", f"{REST_PREFIX}/packages/install", json=body)
        return await self._legacy("InstallPackages", query=query, packages=packages)

    async def remove_packages(self, query: str, packages: list[str]) -> dict:
        if self.is_rest:
            body = {"query": query, "packages": packages}
            return await self._rest("POST", f"{REST_PREFIX}/packages/remove", json=body)
        return await self._legacy("RemovePackages", query=query, packages=packages)

    async def upgrade_packages(
        self, query: str, packages: list[str] | None = None, security_only: bool = False
    ) -> dict:
        # UpgradePackages: omit `packages` to upgrade everything; security_only for USNs.
        if self.is_rest:
            body = {"query": query, "security_only": security_only}
            if packages:
                body["packages"] = packages
            return await self._rest("POST", f"{REST_PREFIX}/packages/upgrade", json=body)
        kwargs: dict[str, Any] = {"query": query, "security_only": security_only}
        if packages:
            kwargs["packages"] = packages
        return await self._legacy("UpgradePackages", **kwargs)

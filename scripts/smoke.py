#!/usr/bin/env python
"""Safe live smoke test for Bob Ross against a real Landscape instance.

Exercises every read tool, resource, and prompt, and verifies the safety layer
blocks writes in read-only mode. It NEVER executes a destructive action — write
tools are only checked for registration and (optionally) dry-run previews.

Usage (from a directory with a configured .env, or with BOBROSS_* env set):

    python scripts/smoke.py

Exits non-zero if anything fails, so it doubles as a post-change check.
"""

from __future__ import annotations

import asyncio
import json
import sys
import warnings

warnings.filterwarnings("ignore")

from bob_ross.client import LandscapeClient  # noqa: E402
from bob_ross.config import Settings  # noqa: E402
from bob_ross.server import build_server  # noqa: E402

results: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}"[:140])


async def call(server, name: str, args: dict):
    r = await server.call_tool(name, args)
    return r.structured_content if r.structured_content is not None else r.data


async def read_resource(server, uri: str):
    rr = await server.read_resource(uri)
    content = rr.model_dump()["contents"][0]["content"]
    return json.loads(content) if isinstance(content, str) else content


async def main() -> int:
    settings = Settings()
    server = build_server(settings)
    read_only_server = build_server(
        Settings(landscape_url=settings.landscape_url, api_token="x")
        if settings.api_token
        else Settings(
            landscape_url=settings.landscape_url,
            access_key=settings.access_key,
            secret_key=settings.secret_key,
            read_only=True,
            allow_writes=False,
        )
    )
    client = LandscapeClient(settings)

    computers = await client.get_computers(limit=5)
    if not computers:
        rec("has computers", False, "no computers returned")
        return 1
    cid = computers[0]["id"]

    # Read tools
    read_checks = [
        ("ping", {}, lambda r: r.get("reachable")),
        ("estate_health", {}, lambda r: "total_computers" in r),
        ("list_computers", {}, lambda r: r.get("count", 0) >= 1),
        ("get_computer", {"computer_id": cid}, lambda r: r.get("title") or r.get("id")),
        ("resolve_query", {"query": f"id:{cid}"}, lambda r: r.get("count") == 1),
        ("pending_updates", {"query": f"id:{cid}"}, lambda r: "total_upgradeable_packages" in r),
        ("list_alerts", {}, lambda r: "count" in r),
        ("list_activities", {"limit": 3}, lambda r: "activities" in r or "count" in r),
        ("list_scripts", {}, lambda r: "scripts" in r or "count" in r),
    ]
    for name, args, check in read_checks:
        try:
            r = await call(server, name, args)
            ok = isinstance(r, dict) and not r.get("error") and bool(check(r))
            rec(name, ok, "" if ok else f"-> {str(r)[:80]}")
        except Exception as exc:  # noqa: BLE001
            rec(name, False, f"EXC {type(exc).__name__}: {exc}")

    # Resources
    for uri in (
        "landscape://computers",
        "landscape://alerts",
        "landscape://health",
        f"landscape://computer/{cid}",
    ):
        try:
            r = await read_resource(server, uri)
            rec(f"resource {uri}", isinstance(r, dict) and not r.get("error"))
        except Exception as exc:  # noqa: BLE001
            rec(f"resource {uri}", False, f"EXC {exc}")

    # Prompts (rendered — the correct API is render_prompt)
    for pname, args in [
        ("patch_security_updates", {"tag": "staging"}),
        ("triage_estate", {}),
        ("reboot_reboot_required", {}),
        ("patch_machine", {"hostname": "example"}),
    ]:
        try:
            rendered = await server.render_prompt(pname, args)
            rec(f"prompt {pname}", bool(rendered.messages))
        except Exception as exc:  # noqa: BLE001
            rec(f"prompt {pname}", False, f"EXC {exc}")

    # Safety: read-only mode must block a write
    try:
        r = await call(read_only_server, "reboot_computers", {"query": f"id:{cid}"})
        rec(
            "safety: read-only blocks writes",
            isinstance(r, dict) and "read-only" in str(r.get("error", "")).lower(),
        )
    except Exception as exc:  # noqa: BLE001
        rec("safety: read-only blocks writes", False, f"EXC {exc}")

    await client.aclose()

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'=' * 50}\nSMOKE: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

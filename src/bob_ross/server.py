"""Bob Ross 🎨 — the FastMCP server.

Read tools are always available. Write tools require BOTH safety switches off
(read_only=false, allow_writes=true) AND a dry-run→confirm handshake.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from .audit import AuditLog
from .client import LandscapeClient, LandscapeError
from .config import Settings
from .safety import ConfirmStore, SafetyError, ensure_writes_enabled

READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}


def _summarise(computers: list[dict]) -> dict:
    """Compact a computer list into id + a human label, tolerant of API shape."""
    out = []
    for c in computers:
        out.append(
            {
                "id": c.get("id") or c.get("computer_id"),
                "title": c.get("title") or c.get("hostname") or c.get("name"),
                "last_ping": c.get("last_ping_time") or c.get("last_seen"),
            }
        )
    return {"count": len(out), "computers": out}


def _ids(computers: list[dict]) -> list:
    return [c.get("id") or c.get("computer_id") for c in computers if (c.get("id") or c.get("computer_id"))]


def build_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings()
    client = LandscapeClient(settings)
    audit = AuditLog(settings.audit_log_path)
    confirm = ConfirmStore(settings.confirm_ttl_seconds)

    @asynccontextmanager
    async def lifespan(_server: FastMCP):
        try:
            yield {}
        finally:
            await client.aclose()

    mcp = FastMCP(
        name="Bob Ross 🎨",
        instructions=(
            "Manage a Canonical Landscape estate. ALWAYS call `resolve_query` to "
            "preview the blast radius before any action. Destructive tools return a "
            "confirm_token on first call (a dry run); call them again with that token "
            "to actually execute. The server may be in read-only mode."
        ),
        lifespan=lifespan,
    )

    # ── helper: uniform error -> audit + agent-facing message ───────
    async def _guarded_read(tool: str, params: dict, coro):
        try:
            result = await coro
            audit.record(tool=tool, outcome="read", params=params)
            return result
        except LandscapeError as exc:
            audit.record(tool=tool, outcome="error", params=params, detail=str(exc))
            return {"error": str(exc)}

    # ─────────────────────────── READ TOOLS ────────────────────────
    @mcp.tool(annotations=READ_ONLY)
    async def ping() -> dict:
        """Check connectivity and that credentials work against Landscape."""
        return await _guarded_read("ping", {}, client.ping())

    @mcp.tool(annotations=READ_ONLY)
    async def list_computers(query: str = "", limit: int = 50, offset: int = 0) -> dict:
        """List computers in the estate. `query` uses Landscape's query language
        (e.g. 'tag:web', 'os:noble', 'alert:security-upgrades')."""
        rows = await _guarded_read(
            "list_computers", {"query": query, "limit": limit},
            client.get_computers(query, limit, offset),
        )
        return rows if isinstance(rows, dict) and "error" in rows else _summarise(rows)

    @mcp.tool(annotations=READ_ONLY)
    async def get_computer(computer_id: int) -> dict:
        """Full detail for a single computer by id."""
        return await _guarded_read(
            "get_computer", {"computer_id": computer_id}, client.get_computer(computer_id)
        )

    @mcp.tool(annotations=READ_ONLY)
    async def resolve_query(query: str) -> dict:
        """Preview the BLAST RADIUS of a query: how many machines it matches and a
        sample of them. Always run this before a destructive action."""
        rows = await _guarded_read(
            "resolve_query", {"query": query}, client.get_computers(query, limit=500)
        )
        if isinstance(rows, dict) and "error" in rows:
            return rows
        summary = _summarise(rows)
        summary["sample"] = summary["computers"][:10]
        summary["computers"] = f"<{summary['count']} matched; showing first 10 in 'sample'>"
        return summary

    @mcp.tool(annotations=READ_ONLY)
    async def list_alerts() -> dict:
        """Active alerts across the estate (pending security upgrades, offline, etc.)."""
        rows = await _guarded_read("list_alerts", {}, client.get_alerts())
        return rows if isinstance(rows, dict) else {"alerts": rows, "count": len(rows)}

    @mcp.tool(annotations=READ_ONLY)
    async def list_activities(query: str = "", limit: int = 50) -> dict:
        """Recent activities (async jobs) and their status. Use to track prior actions."""
        rows = await _guarded_read(
            "list_activities", {"query": query, "limit": limit},
            client.get_activities(query, limit),
        )
        return rows if isinstance(rows, dict) else {"activities": rows, "count": len(rows)}

    @mcp.tool(annotations=READ_ONLY)
    async def get_activity(activity_id: int) -> dict:
        """Status/detail of one activity by id (e.g. to see if a reboot finished)."""
        return await _guarded_read(
            "get_activity", {"activity_id": activity_id}, client.get_activity(activity_id)
        )

    @mcp.tool(annotations=READ_ONLY)
    async def list_scripts() -> dict:
        """Stored scripts available to run via execute_script."""
        rows = await _guarded_read("list_scripts", {}, client.get_scripts())
        return rows if isinstance(rows, dict) else {"scripts": rows, "count": len(rows)}

    # ─────────────────── DESTRUCTIVE TOOLS (gated) ──────────────────
    async def _dry_run_or_execute(
        tool: str, action: str, query: str, confirm_token: str | None, summary_verb: str, run
    ) -> dict:
        """Shared handshake: first call = dry run + token; second = execute."""
        try:
            ensure_writes_enabled(settings)
            targets = await client.get_computers(query, limit=500)
        except (SafetyError, LandscapeError) as exc:
            audit.record(tool=tool, outcome="denied", params={"query": query}, detail=str(exc))
            return {"error": str(exc)}

        ids = _ids(targets)
        summary = f"{summary_verb} on {len(ids)} computer(s) matched by '{query}'"

        if confirm_token is None:
            pending = confirm.issue(action, ids, summary)
            audit.record(tool=tool, outcome="dry_run", params={"query": query}, target_count=len(ids))
            return {
                "status": "confirmation_required",
                "summary": summary,
                "blast_radius": {"count": len(ids), "sample": _summarise(targets)["computers"][:10]},
                "confirm_token": pending.token,
                "expires_in_seconds": settings.confirm_ttl_seconds,
                "next_step": f"Call {tool} again with confirm_token to execute.",
            }

        try:
            confirm.consume(confirm_token, action, ids)
        except SafetyError as exc:
            audit.record(tool=tool, outcome="denied", params={"query": query}, detail=str(exc))
            return {"error": str(exc)}

        try:
            result = await run()
        except LandscapeError as exc:
            audit.record(tool=tool, outcome="error", params={"query": query}, detail=str(exc))
            return {"error": str(exc)}

        audit.record(tool=tool, outcome="executed", params={"query": query}, target_count=len(ids))
        return {"status": "executed", "summary": summary, "target_count": len(ids), "result": result}

    @mcp.tool(annotations=DESTRUCTIVE)
    async def execute_script(
        query: str, script_id: int, username: str = "root", confirm_token: str | None = None
    ) -> dict:
        """Run a stored script on matched machines. Dry run first (omit confirm_token)."""
        return await _dry_run_or_execute(
            "execute_script", "execute_script", query, confirm_token,
            f"Run script {script_id} as {username}",
            lambda: client.execute_script(query, script_id, username),
        )

    @mcp.tool(annotations=DESTRUCTIVE)
    async def reboot_computers(query: str, confirm_token: str | None = None) -> dict:
        """Reboot matched machines. Dry run first (omit confirm_token)."""
        return await _dry_run_or_execute(
            "reboot_computers", "reboot_computers", query, confirm_token,
            "Reboot", lambda: client.reboot_computers(query),
        )

    @mcp.tool(annotations=DESTRUCTIVE)
    async def apply_security_upgrades(query: str, confirm_token: str | None = None) -> dict:
        """Apply pending security (USN) upgrades to matched machines. Dry run first."""
        return await _dry_run_or_execute(
            "apply_security_upgrades", "apply_security_upgrades", query, confirm_token,
            "Apply security upgrades", lambda: client.upgrade_packages(query, security_only=True),
        )

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
    async def add_tags(query: str, tags: list[str], confirm_token: str | None = None) -> dict:
        """Add tags to matched machines (non-destructive, but still write-gated)."""
        return await _dry_run_or_execute(
            "add_tags", "add_tags", query, confirm_token,
            f"Add tags {tags}", lambda: client.add_tags(query, tags),
        )

    # ─────────────────────────── RESOURCES ─────────────────────────
    @mcp.resource("landscape://computers")
    async def computers_resource() -> dict:
        """Cheap read-only snapshot of the estate for grounding context."""
        return _summarise(await client.get_computers(limit=200))

    @mcp.resource("landscape://alerts")
    async def alerts_resource() -> dict:
        """Cheap read-only snapshot of active alerts."""
        rows = await client.get_alerts()
        return {"alerts": rows, "count": len(rows)}

    # ─────────────────────────── PROMPTS ───────────────────────────
    @mcp.prompt
    def patch_security_updates(tag: str = "staging") -> str:
        """Guided workflow to safely apply pending security updates to a tag."""
        return (
            f"Patch pending security updates on machines tagged '{tag}'.\n"
            f"1. Call resolve_query with query 'tag:{tag} alert:security-upgrades' to see the blast radius.\n"
            f"2. Show me the count and sample, then call apply_security_upgrades (dry run).\n"
            f"3. After I approve, re-call with the confirm_token.\n"
            f"4. Poll list_activities to confirm success and report any failures."
        )

    return mcp


mcp = None  # populated by __main__ so importing this module never needs credentials

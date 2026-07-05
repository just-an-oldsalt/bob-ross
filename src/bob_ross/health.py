"""Estate-health summary — pure functions over Landscape data (unit-testable).

Turns raw computers/alerts/activities into a one-shot situational-awareness
report: what's broken, what's stale, what needs patching, ranked into a plain
'attention' list an agent can act on.
"""

from __future__ import annotations

from datetime import datetime


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _title(c: dict) -> str:
    return c.get("title") or c.get("hostname") or c.get("name") or f"id:{c.get('id')}"


def build_health(
    computers: list[dict],
    alerts: list[dict],
    activities: list[dict],
    *,
    now: datetime,
    stale_after_seconds: float,
) -> dict:
    reboot = [c for c in computers if c.get("reboot_required_flag")]

    stale: list[dict] = []
    for c in computers:
        last = _parse_iso(c.get("last_ping_time") or c.get("last_ping"))
        if last is None:
            continue
        age = (now - last).total_seconds()
        if age > stale_after_seconds:
            stale.append(
                {
                    "title": _title(c),
                    "last_ping": c.get("last_ping_time") or c.get("last_ping"),
                    "stale_hours": round(age / 3600, 1),
                }
            )
    stale.sort(key=lambda s: s["stale_hours"], reverse=True)

    distributions: dict[str, int] = {}
    for c in computers:
        d = str(c.get("distribution") or "unknown")
        distributions[d] = distributions.get(d, 0) + 1

    alerts_by_type: dict[str, int] = {}
    for a in alerts:
        t = str(a.get("alert_type") or a.get("type") or "unknown")
        alerts_by_type[t] = alerts_by_type.get(t, 0) + 1

    failed = [
        a
        for a in activities
        if (a.get("activity_status") or "").lower() in {"failed", "canceled", "cancelled"}
    ]

    # Ranked, human-readable "do something about these" list.
    attention: list[str] = []
    for s in stale:
        attention.append(
            f"{s['title']} offline/stale for {s['stale_hours']}h (last ping {s['last_ping']})"
        )
    for c in reboot:
        attention.append(f"{_title(c)} needs a reboot")
    for t, n in sorted(alerts_by_type.items(), key=lambda kv: kv[1], reverse=True):
        if any(k in t.lower() for k in ("security", "upgrade", "package")):
            attention.append(f"{n} alert(s) of type '{t}'")
    for a in failed[:10]:
        attention.append(f"activity {a.get('id')} {a.get('activity_status')}: {a.get('summary')}")

    return {
        "as_of": now.isoformat(),
        "total_computers": len(computers),
        "reboot_required": {"count": len(reboot), "computers": [_title(c) for c in reboot]},
        "stale_or_offline": {
            "count": len(stale),
            "threshold_hours": round(stale_after_seconds / 3600, 1),
            "computers": stale,
        },
        "distributions": distributions,
        "alerts": {"total": len(alerts), "by_type": alerts_by_type},
        "recent_failed_activities": {
            "count": len(failed),
            "activities": [
                {"id": a.get("id"), "status": a.get("activity_status"), "summary": a.get("summary")}
                for a in failed[:10]
            ],
        },
        "attention": attention,
    }

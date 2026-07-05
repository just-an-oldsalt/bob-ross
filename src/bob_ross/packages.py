"""Pure aggregation of Landscape GetPackages results (unit-testable).

A GetPackages(upgrade=true) row looks like:
    {"name": "apt", "version": "2.8.3", "summary": "...",
     "computers": {"available": [2], "installed": [], "upgrades": [2], "held": []}}
`computers.upgrades` lists the computer ids that have a pending upgrade for it.
"""

from __future__ import annotations


def summarize_pending_updates(
    packages: list[dict],
    *,
    id_to_title: dict | None = None,
    sample: int = 50,
) -> dict:
    id_to_title = id_to_title or {}

    def name_of(cid) -> str:
        return id_to_title.get(cid, f"id:{cid}")

    per_computer: dict = {}
    for p in packages:
        for cid in (p.get("computers", {}).get("upgrades") or []):
            per_computer[cid] = per_computer.get(cid, 0) + 1

    per_computer_named = {
        name_of(cid): count
        for cid, count in sorted(per_computer.items(), key=lambda kv: kv[1], reverse=True)
    }

    listed = [
        {
            "name": p.get("name"),
            "version": p.get("version"),
            "summary": p.get("summary"),
            "computers": [name_of(c) for c in (p.get("computers", {}).get("upgrades") or [])],
        }
        for p in packages[:sample]
    ]

    return {
        "total_upgradeable_packages": len(packages),
        "computers_with_updates": len(per_computer),
        "per_computer": per_computer_named,
        "packages": listed,
        "truncated": len(packages) > sample,
    }

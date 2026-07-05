from bob_ross.packages import summarize_pending_updates

PKGS = [
    {
        "name": "apt",
        "version": "2.8.3",
        "summary": "pkg mgr",
        "computers": {"available": [2], "installed": [], "upgrades": [2], "held": []},
    },
    {
        "name": "apparmor",
        "version": "4.0.1",
        "summary": "aa",
        "computers": {"available": [2, 6], "installed": [], "upgrades": [2, 6], "held": []},
    },
    {
        "name": "held-pkg",
        "version": "1.0",
        "summary": "held",
        "computers": {"available": [], "installed": [], "upgrades": [], "held": [6]},
    },
]
TITLES = {2: "kaylee-mc", 6: "grafana"}


def test_totals():
    s = summarize_pending_updates(PKGS, id_to_title=TITLES)
    assert s["total_upgradeable_packages"] == 3
    assert s["computers_with_updates"] == 2  # ids 2 and 6


def test_per_computer_counts_use_titles():
    s = summarize_pending_updates(PKGS, id_to_title=TITLES)
    assert s["per_computer"]["kaylee-mc"] == 2  # apt + apparmor
    assert s["per_computer"]["grafana"] == 1  # apparmor only (held-pkg not in upgrades)


def test_unknown_id_falls_back():
    s = summarize_pending_updates(PKGS)  # no title map
    assert s["per_computer"]["id:2"] == 2


def test_sample_truncation_flagged():
    s = summarize_pending_updates(PKGS, id_to_title=TITLES, sample=1)
    assert s["truncated"] is True
    assert len(s["packages"]) == 1


def test_package_lists_upgrade_computers():
    s = summarize_pending_updates(PKGS, id_to_title=TITLES, sample=50)
    apparmor = next(p for p in s["packages"] if p["name"] == "apparmor")
    assert apparmor["computers"] == ["kaylee-mc", "grafana"]


def test_empty():
    s = summarize_pending_updates([])
    assert s["total_upgradeable_packages"] == 0
    assert s["truncated"] is False

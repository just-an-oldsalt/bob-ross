from datetime import datetime, timezone

from bob_ross.health import build_health

NOW = datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc)

COMPUTERS = [
    {
        "id": 1,
        "title": "maddy-mc",
        "distribution": "24.04",
        "reboot_required_flag": False,
        "last_ping_time": "2026-03-07T03:31:06Z",
    },  # ~120 days stale
    {
        "id": 2,
        "title": "kaylee-mc",
        "distribution": "24.04",
        "reboot_required_flag": False,
        "last_ping_time": "2026-07-05T00:00:00Z",
    },  # fresh
    {
        "id": 6,
        "title": "grafana",
        "distribution": "22.04",
        "reboot_required_flag": True,
        "last_ping_time": "2026-07-04T23:59:00Z",
    },  # fresh, needs reboot
]
ALERTS = [
    {"alert_type": "security-upgrades"},
    {"alert_type": "security-upgrades"},
    {"alert_type": "ComputerOfflineAlert"},
]
ACTIVITIES = [
    {"id": 359, "activity_status": "succeeded", "summary": "ok"},
    {"id": 360, "activity_status": "failed", "summary": "apt lock"},
]


def _health(hours=1.0):
    return build_health(COMPUTERS, ALERTS, ACTIVITIES, now=NOW, stale_after_seconds=hours * 3600)


def test_totals_and_distributions():
    h = _health()
    assert h["total_computers"] == 3
    assert h["distributions"] == {"24.04": 2, "22.04": 1}


def test_reboot_detection():
    h = _health()
    assert h["reboot_required"]["count"] == 1
    assert h["reboot_required"]["computers"] == ["grafana"]


def test_staleness_flags_only_old_machines():
    h = _health(hours=1.0)
    assert h["stale_or_offline"]["count"] == 1
    assert h["stale_or_offline"]["computers"][0]["title"] == "maddy-mc"
    assert h["stale_or_offline"]["computers"][0]["stale_hours"] > 2800  # ~120 days


def test_high_threshold_clears_staleness():
    h = _health(hours=24 * 365)  # a year — nothing counts as stale
    assert h["stale_or_offline"]["count"] == 0


def test_alerts_grouped():
    h = _health()
    assert h["alerts"]["total"] == 3
    assert h["alerts"]["by_type"]["security-upgrades"] == 2


def test_failed_activities_filtered():
    h = _health()
    assert h["recent_failed_activities"]["count"] == 1
    assert h["recent_failed_activities"]["activities"][0]["id"] == 360


def test_attention_list_mentions_key_issues():
    text = " | ".join(_health()["attention"])
    assert "maddy-mc" in text and "reboot" in text and "security-upgrades" in text
    assert "360" in text  # failed activity surfaced

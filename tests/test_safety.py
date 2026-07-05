import pytest

from bob_ross.audit import redact
from bob_ross.config import Settings
from bob_ross.safety import ConfirmStore, SafetyError, ensure_writes_enabled


def _settings(**over):
    base = dict(landscape_url="https://ls.example.com", api_token="t")
    base.update(over)
    return Settings(**base)


def test_writes_blocked_by_default():
    with pytest.raises(SafetyError):
        ensure_writes_enabled(_settings())


def test_writes_need_both_switches():
    with pytest.raises(SafetyError):
        ensure_writes_enabled(_settings(read_only=False))  # allow_writes still False
    with pytest.raises(SafetyError):
        ensure_writes_enabled(_settings(allow_writes=True))  # read_only still True
    # Both flipped -> allowed
    ensure_writes_enabled(_settings(read_only=False, allow_writes=True))


def test_confirm_token_happy_path():
    store = ConfirmStore(ttl_seconds=300)
    pending = store.issue("reboot_computers", [1, 2, 3], "Reboot 3")
    consumed = store.consume(pending.token, "reboot_computers", [3, 2, 1])  # order-insensitive
    assert consumed.target_count == 3


def test_confirm_token_is_single_use():
    store = ConfirmStore(300)
    p = store.issue("reboot_computers", [1], "x")
    store.consume(p.token, "reboot_computers", [1])
    with pytest.raises(SafetyError):
        store.consume(p.token, "reboot_computers", [1])


def test_confirm_token_rejects_target_drift():
    store = ConfirmStore(300)
    p = store.issue("reboot_computers", [1, 2], "x")
    with pytest.raises(SafetyError, match="changed"):
        store.consume(p.token, "reboot_computers", [1, 2, 3])


def test_confirm_token_rejects_wrong_action():
    store = ConfirmStore(300)
    p = store.issue("reboot_computers", [1], "x")
    with pytest.raises(SafetyError, match="different action"):
        store.consume(p.token, "execute_script", [1])


def test_confirm_token_expires():
    store = ConfirmStore(ttl_seconds=-1)  # already expired
    p = store.issue("reboot_computers", [1], "x")
    with pytest.raises(SafetyError, match="expired"):
        store.consume(p.token, "reboot_computers", [1])


def test_redaction():
    out = redact(
        {"secret_key": "abc", "nested": {"api_token": "xyz", "ok": 1}, "list": [{"password": "p"}]}
    )
    assert out["secret_key"] == "***"
    assert out["nested"]["api_token"] == "***"
    assert out["nested"]["ok"] == 1
    assert out["list"][0]["password"] == "***"

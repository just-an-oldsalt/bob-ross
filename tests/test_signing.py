import base64

from bob_ross.client import sign_query

TS = "2026-07-04T12:00:00Z"


def _sign(**params):
    return sign_query("AKID", "secret", "https://ls.example.com", "GetComputers", params, timestamp=TS)


def test_signature_is_deterministic():
    a = _sign(query="tag:web")
    b = _sign(query="tag:web")
    assert a["signature"] == b["signature"]


def test_signature_is_valid_base64():
    sig = _sign(query="tag:web")["signature"]
    assert base64.b64decode(sig)  # does not raise


def test_secret_changes_signature():
    a = sign_query("AKID", "secret1", "https://ls.example.com", "GetComputers", {}, timestamp=TS)
    b = sign_query("AKID", "secret2", "https://ls.example.com", "GetComputers", {}, timestamp=TS)
    assert a["signature"] != b["signature"]


def test_required_params_present():
    signed = _sign(query="x")
    for key in ("action", "access_key_id", "signature_method", "signature_version", "timestamp", "version", "signature"):
        assert key in signed
    assert signed["signature_method"] == "HmacSHA256"


def test_list_params_expand_to_indexed_keys():
    signed = sign_query("AKID", "s", "https://ls.example.com", "AddTagsToComputers", {"tags": ["a", "b"]}, timestamp=TS)
    assert signed["tags.1"] == "a"
    assert signed["tags.2"] == "b"


def test_bool_params_lowercased():
    signed = sign_query("AKID", "s", "https://ls.example.com", "UpgradePackages", {"security_only": True}, timestamp=TS)
    assert signed["security_only"] == "true"

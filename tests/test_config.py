import pytest
from pydantic import ValidationError

from bob_ross.config import AuthMode, Settings


def test_rest_auth_detected():
    s = Settings(landscape_url="https://ls.example.com", api_token="tok")
    assert s.auth_mode == AuthMode.rest


def test_legacy_auth_detected():
    s = Settings(landscape_url="https://ls.example.com", access_key="AK", secret_key="SK")
    assert s.auth_mode == AuthMode.legacy


def test_missing_credentials_rejected():
    with pytest.raises(ValidationError):
        Settings(landscape_url="https://ls.example.com")


def test_bad_url_rejected():
    with pytest.raises(ValidationError):
        Settings(landscape_url="ls.example.com", api_token="tok")


def test_read_only_by_default():
    s = Settings(landscape_url="https://ls.example.com", api_token="tok")
    assert s.read_only is True
    assert s.writes_enabled is False


def test_secrets_not_in_repr():
    s = Settings(landscape_url="https://ls.example.com", api_token="super-secret-token")
    assert "super-secret-token" not in repr(s)

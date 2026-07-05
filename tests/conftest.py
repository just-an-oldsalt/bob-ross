"""Test isolation: never read the developer's real .env or BOBROSS_* env vars.

Without this, `Settings()` in a test would silently pick up live credentials
from .env and mask bugs (e.g. a 'missing credentials' test that never fails).
"""

import os

import pytest

from bob_ross.config import Settings


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("BOBROSS_"):
            monkeypatch.delenv(key, raising=False)
    # Stop pydantic-settings from loading the on-disk .env during tests.
    monkeypatch.setitem(Settings.model_config, "env_file", None)

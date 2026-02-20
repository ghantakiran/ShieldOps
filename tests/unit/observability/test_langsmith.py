"""Tests for LangSmith integration module.

Tests cover:
- init_langsmith with enabled=False
- init_langsmith with empty api_key
- is_enabled returns False by default
"""

import pytest

from shieldops.observability import langsmith as ls_mod
from shieldops.observability.langsmith import (
    init_langsmith,
    is_enabled,
)


@pytest.fixture(autouse=True)
def _reset_langsmith_state():
    """Reset module-level state between tests."""
    orig_client = ls_mod._client
    orig_enabled = ls_mod._enabled
    ls_mod._client = None
    ls_mod._enabled = False
    yield
    ls_mod._client = orig_client
    ls_mod._enabled = orig_enabled


class TestIsEnabledFalseByDefault:
    def test_is_enabled_false_by_default(self) -> None:
        assert is_enabled() is False


class TestInitDisabled:
    def test_init_disabled(self) -> None:
        """When enabled=False, LangSmith stays inactive."""
        init_langsmith(api_key="sk-test-key", enabled=False)
        assert is_enabled() is False
        assert ls_mod._client is None


class TestInitNoApiKey:
    def test_init_no_api_key(self) -> None:
        """When api_key is empty, LangSmith stays inactive."""
        init_langsmith(api_key="", enabled=True)
        assert is_enabled() is False
        assert ls_mod._client is None

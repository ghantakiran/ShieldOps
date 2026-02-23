"""Tests for configuration hot-reload manager.

Covers ConfigChangeEvent model, ReloadableConfig (get/set, callbacks,
wildcard, change history), and HotReloadManager (reload, validation,
secret redaction, file watching, reload count).
"""

from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime
from unittest.mock import MagicMock

from shieldops.config.hot_reload import (
    ConfigChangeEvent,
    HotReloadManager,
    ReloadableConfig,
)

# ---------------------------------------------------------------------------
# ConfigChangeEvent model
# ---------------------------------------------------------------------------


class TestConfigChangeEvent:
    def test_required_key(self):
        event = ConfigChangeEvent(key="my_key")
        assert event.key == "my_key"

    def test_default_old_value_none(self):
        event = ConfigChangeEvent(key="k")
        assert event.old_value is None

    def test_default_new_value_none(self):
        event = ConfigChangeEvent(key="k")
        assert event.new_value is None

    def test_default_source_api(self):
        event = ConfigChangeEvent(key="k")
        assert event.source == "api"

    def test_timestamp_auto_set(self):
        event = ConfigChangeEvent(key="k")
        assert event.timestamp is not None
        assert event.timestamp.tzinfo is not None

    def test_custom_values(self):
        event = ConfigChangeEvent(
            key="db_host",
            old_value="localhost",
            new_value="db.prod.internal",
            source="file",
        )
        assert event.old_value == "localhost"
        assert event.new_value == "db.prod.internal"
        assert event.source == "file"

    def test_serialization(self):
        event = ConfigChangeEvent(key="k", old_value=1, new_value=2)
        data = event.model_dump()
        assert data["key"] == "k"
        assert data["old_value"] == 1
        assert data["new_value"] == 2


# ---------------------------------------------------------------------------
# ReloadableConfig
# ---------------------------------------------------------------------------


class TestReloadableConfigGet:
    def test_get_existing_key(self):
        config = ReloadableConfig({"host": "localhost"})
        assert config.get("host") == "localhost"

    def test_get_missing_key_default_none(self):
        config = ReloadableConfig()
        assert config.get("missing") is None

    def test_get_missing_key_custom_default(self):
        config = ReloadableConfig()
        assert config.get("missing", "fallback") == "fallback"

    def test_get_after_set(self):
        config = ReloadableConfig()
        config.set("key1", "value1")
        assert config.get("key1") == "value1"


class TestReloadableConfigSet:
    def test_set_returns_change_event(self):
        config = ReloadableConfig()
        event = config.set("key1", "value1")
        assert event is not None
        assert isinstance(event, ConfigChangeEvent)
        assert event.key == "key1"
        assert event.new_value == "value1"

    def test_set_same_value_returns_none(self):
        config = ReloadableConfig({"key1": "value1"})
        event = config.set("key1", "value1")
        assert event is None

    def test_set_different_value_returns_event(self):
        config = ReloadableConfig({"key1": "old"})
        event = config.set("key1", "new")
        assert event is not None
        assert event.old_value == "old"
        assert event.new_value == "new"

    def test_set_source_propagated(self):
        config = ReloadableConfig()
        event = config.set("key1", "value1", source="file")
        assert event.source == "file"

    def test_set_none_to_value(self):
        config = ReloadableConfig()
        event = config.set("key1", "value1")
        assert event.old_value is None

    def test_set_value_to_none(self):
        config = ReloadableConfig({"key1": "value1"})
        event = config.set("key1", None)
        assert event is not None
        assert event.new_value is None


class TestReloadableConfigCallbacks:
    def test_on_change_specific_key(self):
        config = ReloadableConfig()
        callback = MagicMock()
        config.on_change("key1", callback)
        config.set("key1", "value1")
        callback.assert_called_once_with("key1", None, "value1")

    def test_on_change_not_called_for_other_keys(self):
        config = ReloadableConfig()
        callback = MagicMock()
        config.on_change("key1", callback)
        config.set("key2", "value2")
        callback.assert_not_called()

    def test_on_change_not_called_when_same_value(self):
        config = ReloadableConfig({"key1": "v"})
        callback = MagicMock()
        config.on_change("key1", callback)
        config.set("key1", "v")
        callback.assert_not_called()

    def test_wildcard_callback(self):
        config = ReloadableConfig()
        callback = MagicMock()
        config.on_change("*", callback)
        config.set("any_key", "value")
        callback.assert_called_once_with("any_key", None, "value")

    def test_wildcard_called_for_all_keys(self):
        config = ReloadableConfig()
        callback = MagicMock()
        config.on_change("*", callback)
        config.set("key1", "v1")
        config.set("key2", "v2")
        assert callback.call_count == 2

    def test_multiple_callbacks_same_key(self):
        config = ReloadableConfig()
        cb1 = MagicMock()
        cb2 = MagicMock()
        config.on_change("key1", cb1)
        config.on_change("key1", cb2)
        config.set("key1", "v")
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_callback_error_does_not_prevent_change(self):
        config = ReloadableConfig()
        bad_cb = MagicMock(side_effect=ValueError("boom"))
        config.on_change("key1", bad_cb)
        event = config.set("key1", "value")
        assert event is not None
        assert config.get("key1") == "value"

    def test_wildcard_callback_error_does_not_prevent_change(self):
        config = ReloadableConfig()
        bad_cb = MagicMock(side_effect=RuntimeError("oops"))
        config.on_change("*", bad_cb)
        event = config.set("key1", "value")
        assert event is not None
        assert config.get("key1") == "value"


class TestReloadableConfigAll:
    def test_all_returns_dict(self):
        config = ReloadableConfig({"a": 1, "b": 2})
        result = config.all()
        assert result == {"a": 1, "b": 2}

    def test_all_returns_copy(self):
        config = ReloadableConfig({"a": 1})
        result = config.all()
        result["a"] = 999
        assert config.get("a") == 1


class TestReloadableConfigChanges:
    def test_changes_initially_empty(self):
        config = ReloadableConfig()
        assert config.changes == []

    def test_changes_recorded(self):
        config = ReloadableConfig()
        config.set("key1", "v1")
        config.set("key2", "v2")
        assert len(config.changes) == 2

    def test_changes_not_recorded_for_same_value(self):
        config = ReloadableConfig({"key1": "v"})
        config.set("key1", "v")
        assert len(config.changes) == 0


# ---------------------------------------------------------------------------
# HotReloadManager
# ---------------------------------------------------------------------------


class TestHotReloadManagerReload:
    def test_reload_applies_changes(self):
        mgr = HotReloadManager(initial_config={"key1": "old"})
        result = mgr.reload({"key1": "new"})
        assert result is True
        assert mgr.config.get("key1") == "new"

    def test_reload_adds_new_keys(self):
        mgr = HotReloadManager(initial_config={"key1": "v1"})
        mgr.reload({"key2": "v2"})
        assert mgr.config.get("key2") == "v2"

    def test_reload_increments_count(self):
        mgr = HotReloadManager()
        assert mgr.reload_count == 0
        mgr.reload({"a": 1})
        assert mgr.reload_count == 1
        mgr.reload({"b": 2})
        assert mgr.reload_count == 2

    def test_reload_sets_last_reload(self):
        mgr = HotReloadManager()
        assert mgr.last_reload is None
        mgr.reload({"a": 1})
        assert mgr.last_reload is not None
        assert isinstance(mgr.last_reload, datetime)

    def test_reload_with_source(self):
        mgr = HotReloadManager()
        mgr.reload({"key1": "v1"}, source="file")
        history = mgr.config.changes
        assert history[0].source == "file"

    def test_reload_no_actual_changes(self):
        mgr = HotReloadManager(initial_config={"key1": "v1"})
        result = mgr.reload({"key1": "v1"})
        assert result is True  # Still counts as reload attempt
        assert mgr.reload_count == 1


class TestHotReloadManagerValidator:
    def test_validator_rejects(self):
        def reject_all(config):
            return False

        mgr = HotReloadManager(validator=reject_all)
        result = mgr.reload({"key1": "v1"})
        assert result is False
        assert mgr.config.get("key1") is None
        assert mgr.reload_count == 0

    def test_validator_accepts(self):
        def accept_all(config):
            return True

        mgr = HotReloadManager(validator=accept_all)
        result = mgr.reload({"key1": "v1"})
        assert result is True
        assert mgr.config.get("key1") == "v1"

    def test_validator_conditional(self):
        def no_empty_values(config):
            return all(v for v in config.values())

        mgr = HotReloadManager(validator=no_empty_values)
        assert mgr.reload({"key1": "ok"}) is True
        assert mgr.reload({"key2": ""}) is False

    def test_no_validator_always_accepts(self):
        mgr = HotReloadManager()
        result = mgr.reload({"anything": "goes"})
        assert result is True


class TestHotReloadManagerRuntimeConfig:
    def test_get_runtime_config_basic(self):
        mgr = HotReloadManager(initial_config={"host": "localhost", "port": 5432})
        config = mgr.get_runtime_config(redact_secrets=False)
        assert config["host"] == "localhost"
        assert config["port"] == 5432

    def test_redact_secrets_password(self):
        mgr = HotReloadManager(initial_config={"db_password": "super-secret"})
        config = mgr.get_runtime_config(redact_secrets=True)
        assert config["db_password"] == "***"  # noqa: S105

    def test_redact_secrets_key(self):
        mgr = HotReloadManager(initial_config={"api_key": "abc123"})
        config = mgr.get_runtime_config()
        assert config["api_key"] == "***"

    def test_redact_secrets_token(self):
        mgr = HotReloadManager(initial_config={"auth_token": "tok_xyz"})
        config = mgr.get_runtime_config()
        assert config["auth_token"] == "***"  # noqa: S105

    def test_redact_secrets_secret(self):
        mgr = HotReloadManager(initial_config={"jwt_secret": "abc"})
        config = mgr.get_runtime_config()
        assert config["jwt_secret"] == "***"  # noqa: S105

    def test_redact_secrets_credential(self):
        mgr = HotReloadManager(initial_config={"aws_credential": "cred"})
        config = mgr.get_runtime_config()
        assert config["aws_credential"] == "***"

    def test_non_secret_not_redacted(self):
        mgr = HotReloadManager(initial_config={"host": "localhost", "api_key": "k"})
        config = mgr.get_runtime_config()
        assert config["host"] == "localhost"

    def test_redact_false_shows_all(self):
        mgr = HotReloadManager(initial_config={"db_password": "secret"})
        config = mgr.get_runtime_config(redact_secrets=False)
        assert config["db_password"] == "secret"  # noqa: S105

    def test_empty_secret_not_redacted(self):
        mgr = HotReloadManager(initial_config={"api_key": ""})
        config = mgr.get_runtime_config()
        # Empty/falsy values are not redacted per the `and v` check
        assert config["api_key"] == ""


class TestHotReloadManagerChangeHistory:
    def test_empty_history(self):
        mgr = HotReloadManager()
        assert mgr.get_change_history() == []

    def test_history_records_changes(self):
        mgr = HotReloadManager()
        mgr.reload({"key1": "v1"})
        history = mgr.get_change_history()
        assert len(history) == 1
        assert history[0]["key"] == "key1"

    def test_history_reversed_order(self):
        mgr = HotReloadManager()
        mgr.reload({"key1": "v1"})
        mgr.reload({"key2": "v2"})
        history = mgr.get_change_history()
        # Most recent first
        assert history[0]["key"] == "key2"
        assert history[1]["key"] == "key1"

    def test_history_limit(self):
        mgr = HotReloadManager()
        for i in range(10):
            mgr.reload({f"key{i}": f"v{i}"})
        history = mgr.get_change_history(limit=3)
        assert len(history) == 3

    def test_history_redacts_secrets(self):
        mgr = HotReloadManager()
        mgr.reload({"db_password": "my_secret"})
        history = mgr.get_change_history()
        assert history[0]["new_value"] == "***"

    def test_history_does_not_redact_non_secrets(self):
        mgr = HotReloadManager()
        mgr.reload({"host": "localhost"})
        history = mgr.get_change_history()
        assert history[0]["new_value"] == "localhost"


class TestHotReloadManagerFileWatcher:
    def test_watch_file_registers_path(self):
        mgr = HotReloadManager()
        mgr.watch_file("/tmp/config.yaml")  # noqa: S108  # nosec B108
        assert "/tmp/config.yaml" in mgr._watchers  # noqa: S108  # nosec B108

    def test_check_files_no_watchers(self):
        mgr = HotReloadManager()
        assert mgr.check_files() == []

    def test_check_files_first_check_no_change(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"key: value\n")
            path = f.name
        try:
            mgr = HotReloadManager()
            mgr.watch_file(path)
            # First check initializes mtime but doesn't report change
            changed = mgr.check_files()
            assert changed == []
        finally:
            os.unlink(path)

    def test_check_files_detects_change(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"key: value\n")
            path = f.name
        try:
            mgr = HotReloadManager()
            mgr.watch_file(path)
            # First check: initializes
            mgr.check_files()

            # Modify the file
            time.sleep(0.05)
            with open(path, "w") as f:
                f.write("key: new_value\n")

            changed = mgr.check_files()
            assert path in changed
        finally:
            os.unlink(path)

    def test_check_files_missing_file_no_error(self):
        mgr = HotReloadManager()
        mgr.watch_file("/nonexistent/path/config.yaml")
        changed = mgr.check_files()
        assert changed == []

    def test_watch_multiple_files(self):
        mgr = HotReloadManager()
        mgr.watch_file("/tmp/a.yaml")  # noqa: S108  # nosec B108
        mgr.watch_file("/tmp/b.yaml")  # noqa: S108  # nosec B108
        assert len(mgr._watchers) == 2


class TestHotReloadManagerReloadCount:
    def test_initial_count_zero(self):
        mgr = HotReloadManager()
        assert mgr.reload_count == 0

    def test_count_increments_on_success(self):
        mgr = HotReloadManager()
        mgr.reload({"a": 1})
        mgr.reload({"b": 2})
        mgr.reload({"c": 3})
        assert mgr.reload_count == 3

    def test_count_does_not_increment_on_validation_failure(self):
        mgr = HotReloadManager(validator=lambda c: False)
        mgr.reload({"a": 1})
        assert mgr.reload_count == 0


class TestHotReloadManagerConfigProperty:
    def test_config_property_returns_reloadable_config(self):
        mgr = HotReloadManager()
        assert isinstance(mgr.config, ReloadableConfig)

    def test_config_property_reflects_initial(self):
        mgr = HotReloadManager(initial_config={"x": 42})
        assert mgr.config.get("x") == 42

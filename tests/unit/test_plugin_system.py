"""Tests for the ShieldOps plugin system -- base classes, registry, loader, and validator."""

from __future__ import annotations

import textwrap
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.plugins.base import (
    AgentPlugin,
    ConnectorPlugin,
    NotificationPlugin,
    PluginMetadata,
    PluginType,
    ScannerPlugin,
    ShieldOpsPlugin,
)
from shieldops.plugins.loader import PluginLoader, PluginLoadError
from shieldops.plugins.registry import PluginRegistry, PluginStatus
from shieldops.plugins.validator import PluginValidator

# ---------------------------------------------------------------------------
# Concrete test plugin implementations
# ---------------------------------------------------------------------------


class FakeConnectorPlugin(ConnectorPlugin):
    """Concrete connector plugin for testing."""

    @property
    def name(self) -> str:
        return "fake-connector"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        self._config = config

    async def teardown(self) -> None:
        pass

    async def connect(self, **kwargs: Any) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def execute_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        return {"output": f"executed: {command}"}


class FakeScannerPlugin(ScannerPlugin):
    """Concrete scanner plugin for testing."""

    @property
    def name(self) -> str:
        return "fake-scanner"

    @property
    def version(self) -> str:
        return "2.3.1"

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def teardown(self) -> None:
        pass

    async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
        return {"target": target, "findings": []}


class FakeNotificationPlugin(NotificationPlugin):
    """Concrete notification plugin for testing."""

    @property
    def name(self) -> str:
        return "fake-notifier"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def teardown(self) -> None:
        pass

    async def send(self, message: str, **kwargs: Any) -> dict[str, Any]:
        return {"sent": True, "message": message}


class FakeAgentPlugin(AgentPlugin):
    """Concrete agent plugin for testing."""

    @property
    def name(self) -> str:
        return "fake-agent"

    @property
    def version(self) -> str:
        return "3.0.0"

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def teardown(self) -> None:
        pass

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"result": "ok", "input": input_data}


class FailingSetupPlugin(ConnectorPlugin):
    """Plugin whose setup() raises an exception."""

    @property
    def name(self) -> str:
        return "failing-setup"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        raise RuntimeError("setup exploded")

    async def teardown(self) -> None:
        pass

    async def connect(self, **kwargs: Any) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def execute_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        return {}


class FailingTeardownPlugin(ScannerPlugin):
    """Plugin whose teardown() raises an exception."""

    @property
    def name(self) -> str:
        return "failing-teardown"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def teardown(self) -> None:
        raise RuntimeError("teardown exploded")

    async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
        return {}


class CustomMetadataPlugin(ScannerPlugin):
    """Plugin that overrides metadata with extra fields."""

    @property
    def name(self) -> str:
        return "custom-meta"

    @property
    def version(self) -> str:
        return "1.2.3"

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version=self.version,
            plugin_type=self.plugin_type,
            description="A custom plugin",
            author="test-author",
            tags=["security", "scanning"],
            requires=["fake-connector"],
        )

    async def setup(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def teardown(self) -> None:
        pass

    async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Helper factory for creating one-off plugin variants (avoids class mutation)
# ---------------------------------------------------------------------------


def _make_scanner_with(
    *,
    name: str = "test-scanner",
    version: str = "1.0.0",
    metadata_override: PluginMetadata | None = None,
    metadata_error: Exception | None = None,
) -> ScannerPlugin:
    """Dynamically create a one-off ScannerPlugin subclass with the given overrides.

    This avoids mutating shared test classes which would leak state between tests.
    """

    # Build the class dict with proper properties
    ns: dict[str, Any] = {
        "name": property(lambda self: name),
        "version": property(lambda self: version),
    }

    if metadata_override is not None:
        ns["metadata"] = property(lambda self: metadata_override)
    elif metadata_error is not None:

        def _raise_meta(self, err=metadata_error):
            raise err

        ns["metadata"] = property(_raise_meta)

    one_off_cls = type(
        "_OneOffScanner",
        (ScannerPlugin,),
        {
            **ns,
            "setup": lambda self, config=None: None,
            "teardown": lambda self: None,
            "scan": lambda self, target, **kw: {"target": target},
        },
    )

    # The methods above are sync; the validator only checks existence/callability,
    # so this is fine for validation tests. For async tests use the full Fake classes.
    return one_off_cls()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture
def validator() -> PluginValidator:
    return PluginValidator()


@pytest.fixture
def connector_plugin() -> FakeConnectorPlugin:
    return FakeConnectorPlugin()


@pytest.fixture
def scanner_plugin() -> FakeScannerPlugin:
    return FakeScannerPlugin()


@pytest.fixture
def notifier_plugin() -> FakeNotificationPlugin:
    return FakeNotificationPlugin()


@pytest.fixture
def agent_plugin() -> FakeAgentPlugin:
    return FakeAgentPlugin()


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


class TestPluginType:
    """Tests for the PluginType enum."""

    def test_plugin_type_has_connector_value(self):
        assert PluginType.CONNECTOR == "connector"

    def test_plugin_type_has_scanner_value(self):
        assert PluginType.SCANNER == "scanner"

    def test_plugin_type_has_notification_value(self):
        assert PluginType.NOTIFICATION == "notification"

    def test_plugin_type_has_agent_value(self):
        assert PluginType.AGENT == "agent"

    def test_plugin_type_has_exactly_four_members(self):
        assert len(PluginType) == 4

    def test_plugin_type_is_str_enum(self):
        assert isinstance(PluginType.CONNECTOR, str)
        assert PluginType.CONNECTOR == "connector"


class TestPluginMetadata:
    """Tests for the PluginMetadata Pydantic model."""

    def test_metadata_with_required_fields_only(self):
        meta = PluginMetadata(
            name="my-plugin",
            version="1.0.0",
            plugin_type=PluginType.SCANNER,
        )
        assert meta.name == "my-plugin"
        assert meta.version == "1.0.0"
        assert meta.plugin_type == PluginType.SCANNER

    def test_metadata_defaults(self):
        meta = PluginMetadata(
            name="my-plugin",
            version="1.0.0",
            plugin_type=PluginType.AGENT,
        )
        assert meta.description == ""
        assert meta.author == ""
        assert meta.tags == []
        assert meta.requires == []

    def test_metadata_with_all_fields(self):
        meta = PluginMetadata(
            name="advanced-scanner",
            version="2.1.0",
            plugin_type=PluginType.SCANNER,
            description="Scans for CVEs",
            author="security-team",
            tags=["cve", "security"],
            requires=["fake-connector"],
        )
        assert meta.description == "Scans for CVEs"
        assert meta.author == "security-team"
        assert meta.tags == ["cve", "security"]
        assert meta.requires == ["fake-connector"]

    def test_metadata_tags_default_is_independent_per_instance(self):
        meta_a = PluginMetadata(name="a", version="1.0.0", plugin_type=PluginType.AGENT)
        meta_b = PluginMetadata(name="b", version="1.0.0", plugin_type=PluginType.AGENT)
        meta_a.tags.append("modified")
        assert meta_b.tags == [], "Default list must not be shared between instances"


class TestShieldOpsPluginABC:
    """Tests for the ShieldOpsPlugin abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        with pytest.raises(TypeError):
            ShieldOpsPlugin()

    def test_connector_plugin_type_is_connector(self, connector_plugin):
        assert connector_plugin.plugin_type == PluginType.CONNECTOR

    def test_scanner_plugin_type_is_scanner(self, scanner_plugin):
        assert scanner_plugin.plugin_type == PluginType.SCANNER

    def test_notification_plugin_type_is_notification(self, notifier_plugin):
        assert notifier_plugin.plugin_type == PluginType.NOTIFICATION

    def test_agent_plugin_type_is_agent(self, agent_plugin):
        assert agent_plugin.plugin_type == PluginType.AGENT

    def test_default_metadata_reflects_properties(self, connector_plugin):
        meta = connector_plugin.metadata
        assert meta.name == connector_plugin.name
        assert meta.version == connector_plugin.version
        assert meta.plugin_type == connector_plugin.plugin_type

    def test_custom_metadata_override(self):
        plugin = CustomMetadataPlugin()
        meta = plugin.metadata
        assert meta.author == "test-author"
        assert meta.tags == ["security", "scanning"]
        assert meta.requires == ["fake-connector"]

    def test_health_check_returns_default_dict(self, scanner_plugin):
        health = scanner_plugin.health_check()
        assert health["status"] == "ok"
        assert health["plugin"] == "fake-scanner"
        assert health["version"] == "2.3.1"


class TestConnectorPluginSubtype:
    """Tests for ConnectorPlugin ABC."""

    @pytest.mark.asyncio
    async def test_connect_is_callable(self, connector_plugin):
        await connector_plugin.connect()

    @pytest.mark.asyncio
    async def test_disconnect_is_callable(self, connector_plugin):
        await connector_plugin.disconnect()

    @pytest.mark.asyncio
    async def test_execute_command_returns_result(self, connector_plugin):
        result = await connector_plugin.execute_command("ls -la")
        assert result == {"output": "executed: ls -la"}


class TestScannerPluginSubtype:
    """Tests for ScannerPlugin ABC."""

    @pytest.mark.asyncio
    async def test_scan_returns_result(self, scanner_plugin):
        result = await scanner_plugin.scan("192.168.1.1")
        assert result["target"] == "192.168.1.1"
        assert isinstance(result["findings"], list)


class TestNotificationPluginSubtype:
    """Tests for NotificationPlugin ABC."""

    @pytest.mark.asyncio
    async def test_send_returns_result(self, notifier_plugin):
        result = await notifier_plugin.send("Alert fired")
        assert result["sent"] is True
        assert result["message"] == "Alert fired"


class TestAgentPluginSubtype:
    """Tests for AgentPlugin ABC."""

    @pytest.mark.asyncio
    async def test_run_returns_result(self, agent_plugin):
        result = await agent_plugin.run({"query": "investigate"})
        assert result["result"] == "ok"
        assert result["input"] == {"query": "investigate"}


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------


class TestPluginRegistryRegister:
    """Tests for PluginRegistry.register()."""

    @pytest.mark.asyncio
    async def test_register_creates_plugin_status(self, registry, connector_plugin):
        status = await registry.register(connector_plugin)
        assert isinstance(status, PluginStatus)
        assert status.name == "fake-connector"
        assert status.version == "1.0.0"
        assert status.plugin_type == PluginType.CONNECTOR
        assert status.enabled is True
        assert status.error is None

    @pytest.mark.asyncio
    async def test_register_with_auto_setup_calls_setup(self, registry):
        plugin = FakeConnectorPlugin()
        plugin.setup = AsyncMock()
        config = {"host": "localhost"}

        await registry.register(plugin, config=config, auto_setup=True)

        plugin.setup.assert_awaited_once_with(config)

    @pytest.mark.asyncio
    async def test_register_without_auto_setup_does_not_call_setup(self, registry):
        plugin = FakeConnectorPlugin()
        plugin.setup = AsyncMock()

        await registry.register(plugin, auto_setup=False)

        plugin.setup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_register_with_setup_failure_sets_enabled_false(self, registry):
        plugin = FailingSetupPlugin()
        status = await registry.register(plugin)
        assert status.enabled is False
        assert status.error == "setup exploded"

    @pytest.mark.asyncio
    async def test_register_with_setup_failure_still_registers_plugin(self, registry):
        plugin = FailingSetupPlugin()
        await registry.register(plugin)
        assert registry.is_registered("failing-setup")

    @pytest.mark.asyncio
    async def test_register_duplicate_returns_existing_status(self, registry, connector_plugin):
        status1 = await registry.register(connector_plugin)
        status2 = await registry.register(connector_plugin)
        assert status1 is status2

    @pytest.mark.asyncio
    async def test_register_stores_config(self, registry, connector_plugin):
        config = {"timeout": 30, "retries": 3}
        status = await registry.register(connector_plugin, config=config)
        assert status.config == config

    @pytest.mark.asyncio
    async def test_register_with_no_config_stores_empty_dict(self, registry, connector_plugin):
        status = await registry.register(connector_plugin)
        assert status.config == {}


class TestPluginRegistryUnregister:
    """Tests for PluginRegistry.unregister()."""

    @pytest.mark.asyncio
    async def test_unregister_calls_teardown_and_removes(self, registry):
        plugin = FakeConnectorPlugin()
        plugin.teardown = AsyncMock()
        await registry.register(plugin, auto_setup=False)

        result = await registry.unregister("fake-connector")

        assert result is True
        plugin.teardown.assert_awaited_once()
        assert not registry.is_registered("fake-connector")

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_returns_false(self, registry):
        result = await registry.unregister("no-such-plugin")
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_with_teardown_error_still_removes(self, registry):
        plugin = FailingTeardownPlugin()
        await registry.register(plugin, auto_setup=False)

        result = await registry.unregister("failing-teardown")

        assert result is True
        assert not registry.is_registered("failing-teardown")


class TestPluginRegistryEnableDisable:
    """Tests for PluginRegistry.enable() and disable()."""

    @pytest.mark.asyncio
    async def test_disable_sets_enabled_false(self, registry, scanner_plugin):
        await registry.register(scanner_plugin, auto_setup=False)
        result = await registry.disable("fake-scanner")
        assert result is True
        status = registry.get_status("fake-scanner")
        assert status.enabled is False

    @pytest.mark.asyncio
    async def test_enable_after_disable_sets_enabled_true(self, registry):
        plugin = FakeScannerPlugin()
        plugin.setup = AsyncMock()
        await registry.register(plugin, auto_setup=False)
        await registry.disable("fake-scanner")

        result = await registry.enable("fake-scanner")

        assert result is True
        status = registry.get_status("fake-scanner")
        assert status.enabled is True
        assert status.error is None

    @pytest.mark.asyncio
    async def test_enable_calls_setup_with_stored_config(self, registry):
        plugin = FakeConnectorPlugin()
        plugin.setup = AsyncMock()
        config = {"host": "localhost"}
        await registry.register(plugin, config=config, auto_setup=False)
        await registry.disable("fake-connector")

        await registry.enable("fake-connector")

        plugin.setup.assert_awaited_with(config)

    @pytest.mark.asyncio
    async def test_enable_with_setup_failure_returns_false(self, registry):
        plugin = FailingSetupPlugin()
        await registry.register(plugin, auto_setup=False)
        await registry.disable("failing-setup")

        result = await registry.enable("failing-setup")

        assert result is False
        status = registry.get_status("failing-setup")
        assert status.enabled is False
        assert status.error == "setup exploded"

    @pytest.mark.asyncio
    async def test_enable_already_enabled_returns_true(self, registry, connector_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        result = await registry.enable("fake-connector")
        assert result is True

    @pytest.mark.asyncio
    async def test_disable_already_disabled_returns_true(self, registry, connector_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        await registry.disable("fake-connector")
        result = await registry.disable("fake-connector")
        assert result is True

    @pytest.mark.asyncio
    async def test_enable_nonexistent_returns_false(self, registry):
        result = await registry.enable("no-such-plugin")
        assert result is False

    @pytest.mark.asyncio
    async def test_disable_nonexistent_returns_false(self, registry):
        result = await registry.disable("no-such-plugin")
        assert result is False

    @pytest.mark.asyncio
    async def test_disable_calls_teardown(self, registry):
        plugin = FakeConnectorPlugin()
        plugin.teardown = AsyncMock()
        await registry.register(plugin, auto_setup=False)

        await registry.disable("fake-connector")

        plugin.teardown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disable_with_teardown_error_still_disables(self, registry):
        plugin = FailingTeardownPlugin()
        await registry.register(plugin, auto_setup=False)

        result = await registry.disable("failing-teardown")

        assert result is True
        status = registry.get_status("failing-teardown")
        assert status.enabled is False


class TestPluginRegistryLookups:
    """Tests for get_plugin(), get_status(), is_registered(), list_plugins()."""

    @pytest.mark.asyncio
    async def test_get_plugin_returns_instance(self, registry, connector_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        plugin = registry.get_plugin("fake-connector")
        assert plugin is connector_plugin

    @pytest.mark.asyncio
    async def test_get_plugin_nonexistent_returns_none(self, registry):
        assert registry.get_plugin("missing") is None

    @pytest.mark.asyncio
    async def test_get_status_returns_status(self, registry, connector_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        status = registry.get_status("fake-connector")
        assert isinstance(status, PluginStatus)
        assert status.name == "fake-connector"

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_returns_none(self, registry):
        assert registry.get_status("missing") is None

    @pytest.mark.asyncio
    async def test_is_registered_true(self, registry, connector_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        assert registry.is_registered("fake-connector") is True

    @pytest.mark.asyncio
    async def test_is_registered_false(self, registry):
        assert registry.is_registered("missing") is False

    @pytest.mark.asyncio
    async def test_list_plugins_returns_all(self, registry, connector_plugin, scanner_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        await registry.register(scanner_plugin, auto_setup=False)
        result = registry.list_plugins()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_plugins_filter_by_type(self, registry, connector_plugin, scanner_plugin):
        await registry.register(connector_plugin, auto_setup=False)
        await registry.register(scanner_plugin, auto_setup=False)
        connectors = registry.list_plugins(plugin_type=PluginType.CONNECTOR)
        assert len(connectors) == 1
        assert connectors[0].name == "fake-connector"

    @pytest.mark.asyncio
    async def test_list_plugins_filter_enabled_only(
        self, registry, connector_plugin, scanner_plugin
    ):
        await registry.register(connector_plugin, auto_setup=False)
        await registry.register(scanner_plugin, auto_setup=False)
        await registry.disable("fake-scanner")
        enabled = registry.list_plugins(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].name == "fake-connector"

    @pytest.mark.asyncio
    async def test_list_plugins_combined_filters(self, registry):
        connector = FakeConnectorPlugin()
        scanner = FakeScannerPlugin()
        notifier = FakeNotificationPlugin()
        await registry.register(connector, auto_setup=False)
        await registry.register(scanner, auto_setup=False)
        await registry.register(notifier, auto_setup=False)
        await registry.disable("fake-scanner")

        result = registry.list_plugins(plugin_type=PluginType.SCANNER, enabled_only=True)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_plugins_empty_registry(self, registry):
        assert registry.list_plugins() == []


class TestPluginRegistryTeardownAll:
    """Tests for PluginRegistry.teardown_all()."""

    @pytest.mark.asyncio
    async def test_teardown_all_removes_all_plugins(self, registry):
        await registry.register(FakeConnectorPlugin(), auto_setup=False)
        await registry.register(FakeScannerPlugin(), auto_setup=False)
        await registry.register(FakeNotificationPlugin(), auto_setup=False)

        await registry.teardown_all()

        assert registry.list_plugins() == []
        assert not registry.is_registered("fake-connector")
        assert not registry.is_registered("fake-scanner")
        assert not registry.is_registered("fake-notifier")

    @pytest.mark.asyncio
    async def test_teardown_all_calls_teardown_on_each(self, registry):
        p1 = FakeConnectorPlugin()
        p1.teardown = AsyncMock()
        p2 = FakeScannerPlugin()
        p2.teardown = AsyncMock()
        await registry.register(p1, auto_setup=False)
        await registry.register(p2, auto_setup=False)

        await registry.teardown_all()

        p1.teardown.assert_awaited_once()
        p2.teardown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_teardown_all_on_empty_registry(self, registry):
        # Should not raise
        await registry.teardown_all()


# ---------------------------------------------------------------------------
# PluginValidator
# ---------------------------------------------------------------------------


class TestPluginValidatorHappyPath:
    """Tests for PluginValidator.validate() with valid plugins."""

    def test_valid_connector_plugin_returns_no_errors(self, validator, connector_plugin):
        errors = validator.validate(connector_plugin)
        assert errors == []

    def test_valid_scanner_plugin_returns_no_errors(self, validator, scanner_plugin):
        errors = validator.validate(scanner_plugin)
        assert errors == []

    def test_valid_notification_plugin_returns_no_errors(self, validator, notifier_plugin):
        errors = validator.validate(notifier_plugin)
        assert errors == []

    def test_valid_agent_plugin_returns_no_errors(self, validator, agent_plugin):
        errors = validator.validate(agent_plugin)
        assert errors == []


class TestPluginValidatorName:
    """Tests for name validation rules."""

    @pytest.mark.parametrize(
        "name",
        [
            "ab",  # minimum length (2 chars)
            "my-plugin",  # typical name with hyphens
            "scanner-v2",  # letters, hyphens, numbers
            "a" * 64,  # maximum length (64 chars)
            "a1",  # letter + number
        ],
    )
    def test_valid_names_pass(self, validator, name):
        plugin = _make_scanner_with(name=name)
        errors = validator.validate(plugin)
        name_errors = [e for e in errors if "name" in e.lower()]
        assert name_errors == [], f"Name '{name}' should be valid, got: {name_errors}"

    @pytest.mark.parametrize(
        "name,reason",
        [
            ("A", "single uppercase char, too short"),
            ("x", "single char is only 1 char (needs 2-64)"),
            ("My-Plugin", "uppercase letters"),
            ("my_plugin", "underscores not allowed"),
            ("123-plugin", "starts with a number"),
            ("-my-plugin", "starts with a hyphen"),
            ("my plugin", "contains a space"),
            ("a" * 65, "exceeds 64 chars"),
        ],
    )
    def test_invalid_names_produce_errors(self, validator, name, reason):
        plugin = _make_scanner_with(name=name)
        errors = validator.validate(plugin)
        name_errors = [e for e in errors if "name" in e.lower()]
        assert len(name_errors) > 0, f"Name '{name}' should be invalid ({reason})"

    def test_empty_name_produces_error(self, validator):
        plugin = _make_scanner_with(name="")
        errors = validator.validate(plugin)
        name_errors = [e for e in errors if "name" in e.lower()]
        assert len(name_errors) > 0


class TestPluginValidatorVersion:
    """Tests for semver version validation."""

    @pytest.mark.parametrize(
        "version",
        [
            "0.0.1",
            "1.0.0",
            "12.34.56",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0+build.123",
            "1.0.0-rc.1+build.456",
        ],
    )
    def test_valid_semver_passes(self, validator, version):
        plugin = _make_scanner_with(version=version)
        errors = validator.validate(plugin)
        version_errors = [e for e in errors if "version" in e.lower()]
        assert version_errors == [], f"Version '{version}' should be valid"

    @pytest.mark.parametrize(
        "version,reason",
        [
            ("1.0", "missing patch number"),
            ("1", "only major number"),
            ("v1.0.0", "leading 'v' prefix"),
            ("1.0.0.0", "too many segments"),
            ("abc", "non-numeric"),
        ],
    )
    def test_invalid_semver_produces_errors(self, validator, version, reason):
        plugin = _make_scanner_with(version=version)
        errors = validator.validate(plugin)
        version_errors = [e for e in errors if "version" in e.lower()]
        assert len(version_errors) > 0, f"Version '{version}' should be invalid ({reason})"

    def test_empty_version_produces_error(self, validator):
        plugin = _make_scanner_with(version="")
        errors = validator.validate(plugin)
        version_errors = [e for e in errors if "version" in e.lower()]
        assert len(version_errors) > 0


class TestPluginValidatorType:
    """Tests for plugin type validation."""

    def test_valid_plugin_types_accepted(self, validator):
        for plugin_cls in (
            FakeConnectorPlugin,
            FakeScannerPlugin,
            FakeNotificationPlugin,
            FakeAgentPlugin,
        ):
            plugin = plugin_cls()
            errors = validator.validate(plugin)
            type_errors = [e for e in errors if "type" in e.lower()]
            assert type_errors == [], f"{plugin_cls.__name__} type should be valid"

    def test_invalid_plugin_type_produces_error(self, validator):
        # Create a one-off class that returns an invalid plugin_type
        class BadTypePlugin(ScannerPlugin):
            @property
            def name(self):
                return "bad-type"

            @property
            def version(self):
                return "1.0.0"

            @property
            def plugin_type(self):
                return "unknown-type"

            async def setup(self, config=None):
                pass

            async def teardown(self):
                pass

            async def scan(self, target, **kwargs):
                return {}

        plugin = BadTypePlugin()
        errors = validator.validate(plugin)
        type_errors = [e for e in errors if "type" in e.lower()]
        assert len(type_errors) > 0


class TestPluginValidatorMethods:
    """Tests for required method validation per plugin type."""

    def test_connector_missing_execute_command_produces_error(self, validator):
        # Build a plugin where execute_command is set to None (not callable)
        plugin = FakeConnectorPlugin()
        plugin.execute_command = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "execute_command" in e]
        assert len(method_errors) > 0

    def test_connector_missing_connect_produces_error(self, validator):
        plugin = FakeConnectorPlugin()
        plugin.connect = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "connect" in e]
        assert len(method_errors) > 0

    def test_connector_missing_disconnect_produces_error(self, validator):
        plugin = FakeConnectorPlugin()
        plugin.disconnect = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "disconnect" in e]
        assert len(method_errors) > 0

    def test_scanner_missing_scan_produces_error(self, validator):
        plugin = FakeScannerPlugin()
        plugin.scan = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "scan" in e]
        assert len(method_errors) > 0

    def test_notification_missing_send_produces_error(self, validator):
        plugin = FakeNotificationPlugin()
        plugin.send = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "send" in e]
        assert len(method_errors) > 0

    def test_agent_missing_run_produces_error(self, validator):
        plugin = FakeAgentPlugin()
        plugin.run = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "run" in e]
        assert len(method_errors) > 0

    def test_base_missing_setup_produces_error(self, validator):
        plugin = FakeConnectorPlugin()
        plugin.setup = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "setup" in e]
        assert len(method_errors) > 0

    def test_base_missing_teardown_produces_error(self, validator):
        plugin = FakeConnectorPlugin()
        plugin.teardown = None  # type: ignore[assignment]
        errors = validator.validate(plugin)
        method_errors = [e for e in errors if "teardown" in e]
        assert len(method_errors) > 0


class TestPluginValidatorMetadata:
    """Tests for metadata consistency validation."""

    def test_consistent_metadata_passes(self, validator, connector_plugin):
        errors = validator.validate(connector_plugin)
        meta_errors = [e for e in errors if "metadata" in e.lower() or "Metadata" in e]
        assert meta_errors == []

    def test_metadata_name_mismatch_produces_error(self, validator):
        plugin = _make_scanner_with(
            name="real-name",
            metadata_override=PluginMetadata(
                name="wrong-name",
                version="1.0.0",
                plugin_type=PluginType.SCANNER,
            ),
        )
        errors = validator.validate(plugin)
        meta_errors = [e for e in errors if "name" in e.lower() and "match" in e.lower()]
        assert len(meta_errors) > 0

    def test_metadata_version_mismatch_produces_error(self, validator):
        plugin = _make_scanner_with(
            name="version-test",
            version="1.0.0",
            metadata_override=PluginMetadata(
                name="version-test",
                version="9.9.9",
                plugin_type=PluginType.SCANNER,
            ),
        )
        errors = validator.validate(plugin)
        meta_errors = [e for e in errors if "version" in e.lower() and "match" in e.lower()]
        assert len(meta_errors) > 0

    def test_metadata_property_exception_captured(self, validator):
        plugin = _make_scanner_with(
            name="error-meta",
            metadata_error=RuntimeError("metadata broken"),
        )
        errors = validator.validate(plugin)
        meta_errors = [e for e in errors if "metadata" in e.lower()]
        assert len(meta_errors) > 0


# ---------------------------------------------------------------------------
# PluginLoader
# ---------------------------------------------------------------------------


class TestPluginLoaderFromDirectory:
    """Tests for PluginLoader.load_from_directory()."""

    @pytest.mark.asyncio
    async def test_load_from_directory_discovers_plugins(self, registry, tmp_path):
        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text(
            textwrap.dedent("""\
            from shieldops.plugins.base import ScannerPlugin
            from typing import Any

            class MyScannerPlugin(ScannerPlugin):
                @property
                def name(self) -> str:
                    return "my-scanner"
                @property
                def version(self) -> str:
                    return "1.0.0"
                async def setup(self, config=None) -> None:
                    pass
                async def teardown(self) -> None:
                    pass
                async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
                    return {}
        """)
        )

        loader = PluginLoader(registry)
        loaded = await loader.load_from_directory(tmp_path)

        assert "my-scanner" in loaded
        assert registry.is_registered("my-scanner")

    @pytest.mark.asyncio
    async def test_load_from_directory_skips_underscore_files(self, registry, tmp_path):
        (tmp_path / "__init__.py").write_text("# init")
        (tmp_path / "_private.py").write_text("# private")

        loader = PluginLoader(registry)
        loaded = await loader.load_from_directory(tmp_path)

        assert loaded == []

    @pytest.mark.asyncio
    async def test_load_from_nonexistent_directory_returns_empty(self, registry, tmp_path):
        loader = PluginLoader(registry)
        loaded = await loader.load_from_directory(tmp_path / "no-such-dir")
        assert loaded == []

    @pytest.mark.asyncio
    async def test_load_from_directory_skips_invalid_plugins(self, registry, tmp_path):
        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text(
            textwrap.dedent("""\
            from shieldops.plugins.base import ScannerPlugin
            from typing import Any

            class BadPlugin(ScannerPlugin):
                @property
                def name(self) -> str:
                    return "BAD_NAME"
                @property
                def version(self) -> str:
                    return "1.0.0"
                async def setup(self, config=None) -> None:
                    pass
                async def teardown(self) -> None:
                    pass
                async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
                    return {}
        """)
        )

        loader = PluginLoader(registry)
        loaded = await loader.load_from_directory(tmp_path)

        assert loaded == []

    @pytest.mark.asyncio
    async def test_load_from_directory_passes_per_plugin_config(self, registry, tmp_path):
        plugin_file = tmp_path / "conf_plugin.py"
        plugin_file.write_text(
            textwrap.dedent("""\
            from shieldops.plugins.base import ScannerPlugin
            from typing import Any

            class ConfPlugin(ScannerPlugin):
                @property
                def name(self) -> str:
                    return "conf-scanner"
                @property
                def version(self) -> str:
                    return "1.0.0"
                async def setup(self, config=None) -> None:
                    self._config = config
                async def teardown(self) -> None:
                    pass
                async def scan(self, target: str, **kwargs: Any) -> dict[str, Any]:
                    return {}
        """)
        )

        config = {"conf-scanner": {"api_key": "secret"}}
        loader = PluginLoader(registry)
        loaded = await loader.load_from_directory(tmp_path, config=config)

        assert "conf-scanner" in loaded
        status = registry.get_status("conf-scanner")
        assert status.config == {"api_key": "secret"}


class TestPluginLoaderFromPackage:
    """Tests for PluginLoader.load_from_package()."""

    @pytest.mark.asyncio
    async def test_load_from_package_with_create_plugin_factory(self, registry):
        fake_plugin = FakeScannerPlugin()
        mock_module = MagicMock(spec=[])
        mock_module.create_plugin = MagicMock(return_value=fake_plugin)

        loader = PluginLoader(registry)
        with patch("shieldops.plugins.loader.importlib.import_module", return_value=mock_module):
            name = await loader.load_from_package("my_package")

        assert name == "fake-scanner"
        assert registry.is_registered("fake-scanner")

    @pytest.mark.asyncio
    async def test_load_from_package_with_plugin_class(self, registry):
        mock_module = MagicMock(spec=[])
        mock_module.Plugin = FakeScannerPlugin

        loader = PluginLoader(registry)
        with patch("shieldops.plugins.loader.importlib.import_module", return_value=mock_module):
            name = await loader.load_from_package("my_package")

        assert name == "fake-scanner"

    @pytest.mark.asyncio
    async def test_load_from_package_import_error_returns_none(self, registry):
        loader = PluginLoader(registry)
        with patch(
            "shieldops.plugins.loader.importlib.import_module",
            side_effect=ImportError("no such module"),
        ):
            result = await loader.load_from_package("nonexistent.package")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_from_package_no_entry_point_returns_none(self, registry):
        mock_module = MagicMock(spec=[])
        # Module has neither create_plugin nor Plugin

        loader = PluginLoader(registry)
        with patch("shieldops.plugins.loader.importlib.import_module", return_value=mock_module):
            result = await loader.load_from_package("empty_package")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_from_package_invalid_plugin_returns_none(self, registry):

        class BadNamePlugin(ScannerPlugin):
            @property
            def name(self) -> str:
                return "BAD"

            @property
            def version(self) -> str:
                return "1.0.0"

            async def setup(self, config=None):
                pass

            async def teardown(self):
                pass

            async def scan(self, target, **kwargs):
                return {}

        mock_module = MagicMock(spec=[])
        mock_module.create_plugin = MagicMock(return_value=BadNamePlugin())

        loader = PluginLoader(registry)
        with patch("shieldops.plugins.loader.importlib.import_module", return_value=mock_module):
            result = await loader.load_from_package("bad_package")

        assert result is None


class TestPluginLoadError:
    """Tests for the PluginLoadError exception class."""

    def test_plugin_load_error_is_exception(self):
        assert issubclass(PluginLoadError, Exception)

    def test_plugin_load_error_carries_message(self):
        err = PluginLoadError("failed to load plugin")
        assert str(err) == "failed to load plugin"

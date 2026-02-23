"""Tests for shieldops.api.contract_testing — APIContractTestingEngine."""

from __future__ import annotations

from shieldops.api.contract_testing import (
    APIContractTestingEngine,
    BreakingChange,
    BreakingChangeType,
    CompatibilityCheck,
    CompatibilityResult,
    SchemaFormat,
    SchemaVersion,
)


def _engine(**kw) -> APIContractTestingEngine:
    return APIContractTestingEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_breaking_field_removed(self):
        assert BreakingChangeType.FIELD_REMOVED == "field_removed"

    def test_breaking_type_changed(self):
        assert BreakingChangeType.TYPE_CHANGED == "type_changed"

    def test_breaking_required_added(self):
        assert BreakingChangeType.REQUIRED_ADDED == "required_added"

    def test_breaking_enum_removed(self):
        assert BreakingChangeType.ENUM_VALUE_REMOVED == "enum_value_removed"

    def test_breaking_path_removed(self):
        assert BreakingChangeType.PATH_REMOVED == "path_removed"

    def test_compat_compatible(self):
        assert CompatibilityResult.COMPATIBLE == "compatible"

    def test_compat_backward(self):
        assert CompatibilityResult.BACKWARD_COMPATIBLE == "backward_compatible"

    def test_compat_breaking(self):
        assert CompatibilityResult.BREAKING == "breaking"

    def test_compat_unknown(self):
        assert CompatibilityResult.UNKNOWN == "unknown"

    def test_format_openapi(self):
        assert SchemaFormat.OPENAPI_3 == "openapi_3"

    def test_format_json_schema(self):
        assert SchemaFormat.JSON_SCHEMA == "json_schema"

    def test_format_protobuf(self):
        assert SchemaFormat.PROTOBUF == "protobuf"

    def test_format_graphql(self):
        assert SchemaFormat.GRAPHQL_SDL == "graphql_sdl"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_schema_version_defaults(self):
        sv = SchemaVersion(api_name="user-api", version="1.0")
        assert sv.id
        assert sv.api_name == "user-api"
        assert sv.schema_format == SchemaFormat.OPENAPI_3
        assert sv.schema_content == {}

    def test_compatibility_check_defaults(self):
        cc = CompatibilityCheck(api_name="user-api", from_version="1.0", to_version="2.0")
        assert cc.result == CompatibilityResult.UNKNOWN
        assert cc.breaking_changes == []

    def test_breaking_change_defaults(self):
        bc = BreakingChange(api_name="user-api", change_type=BreakingChangeType.FIELD_REMOVED)
        assert bc.path == ""
        assert bc.description == ""


# ---------------------------------------------------------------------------
# register_schema
# ---------------------------------------------------------------------------


class TestRegisterSchema:
    def test_basic_register(self):
        eng = _engine()
        schema = eng.register_schema("user-api", "1.0")
        assert schema.api_name == "user-api"
        assert schema.version == "1.0"
        assert eng.get_schema(schema.id) is not None

    def test_unique_ids(self):
        eng = _engine()
        s1 = eng.register_schema("api-a", "1.0")
        s2 = eng.register_schema("api-b", "1.0")
        assert s1.id != s2.id

    def test_with_content(self):
        eng = _engine()
        schema = eng.register_schema("user-api", "1.0", schema_content={"name": "string"})
        assert schema.schema_content == {"name": "string"}

    def test_evicts_at_max(self):
        eng = _engine(max_schemas=2)
        s1 = eng.register_schema("api-1", "1.0")
        eng.register_schema("api-2", "1.0")
        eng.register_schema("api-3", "1.0")
        assert eng.get_schema(s1.id) is None


# ---------------------------------------------------------------------------
# list_versions / get_latest_version
# ---------------------------------------------------------------------------


class TestListVersions:
    def test_list_by_api(self):
        eng = _engine()
        eng.register_schema("user-api", "1.0")
        eng.register_schema("user-api", "2.0")
        eng.register_schema("billing-api", "1.0")
        versions = eng.list_versions("user-api")
        assert len(versions) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.list_versions("nonexistent") == []


class TestGetLatestVersion:
    def test_latest(self):
        eng = _engine()
        eng.register_schema("user-api", "1.0")
        eng.register_schema("user-api", "2.0")
        latest = eng.get_latest_version("user-api")
        assert latest is not None
        assert latest.version == "2.0"

    def test_no_schemas(self):
        eng = _engine()
        assert eng.get_latest_version("nonexistent") is None


# ---------------------------------------------------------------------------
# check_compatibility
# ---------------------------------------------------------------------------


class TestCheckCompatibility:
    def test_compatible(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "string"})
        eng.register_schema("api", "2.0", schema_content={"name": "string"})
        check = eng.check_compatibility("api", "1.0", "2.0")
        assert check.result == CompatibilityResult.COMPATIBLE

    def test_backward_compatible(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "string"})
        eng.register_schema("api", "2.0", schema_content={"name": "string", "email": "string"})
        check = eng.check_compatibility("api", "1.0", "2.0")
        assert check.result == CompatibilityResult.BACKWARD_COMPATIBLE

    def test_breaking(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "string", "age": "int"})
        eng.register_schema("api", "2.0", schema_content={"name": "string"})
        check = eng.check_compatibility("api", "1.0", "2.0")
        assert check.result == CompatibilityResult.BREAKING

    def test_unknown_missing_schema(self):
        eng = _engine()
        check = eng.check_compatibility("api", "1.0", "2.0")
        assert check.result == CompatibilityResult.UNKNOWN


# ---------------------------------------------------------------------------
# detect_breaking_changes
# ---------------------------------------------------------------------------


class TestDetectBreakingChanges:
    def test_field_removed(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "str", "age": "int"})
        eng.register_schema("api", "2.0", schema_content={"name": "str"})
        changes = eng.detect_breaking_changes("api", "1.0", "2.0")
        assert len(changes) == 1
        assert changes[0].change_type == BreakingChangeType.FIELD_REMOVED

    def test_type_changed(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"count": 42})
        eng.register_schema("api", "2.0", schema_content={"count": "forty-two"})
        changes = eng.detect_breaking_changes("api", "1.0", "2.0")
        assert len(changes) == 1
        assert changes[0].change_type == BreakingChangeType.TYPE_CHANGED

    def test_no_changes(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "str"})
        eng.register_schema("api", "2.0", schema_content={"name": "str"})
        changes = eng.detect_breaking_changes("api", "1.0", "2.0")
        assert len(changes) == 0


# ---------------------------------------------------------------------------
# schema_drift / delete / stats
# ---------------------------------------------------------------------------


class TestSchemaDrift:
    def test_no_drift(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "str"})
        eng.register_schema("api", "2.0", schema_content={"name": "str"})
        drift = eng.get_schema_drift("api")
        assert drift["drift_detected"] is False

    def test_drift_detected(self):
        eng = _engine()
        eng.register_schema("api", "1.0", schema_content={"name": "str", "age": "int"})
        eng.register_schema("api", "2.0", schema_content={"name": "str"})
        drift = eng.get_schema_drift("api")
        assert drift["drift_detected"] is True


class TestDeleteSchema:
    def test_delete(self):
        eng = _engine()
        schema = eng.register_schema("api", "1.0")
        assert eng.delete_schema(schema.id) is True
        assert eng.get_schema(schema.id) is None

    def test_delete_not_found(self):
        eng = _engine()
        assert eng.delete_schema("nonexistent") is False


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_schemas"] == 0
        assert stats["total_checks"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.register_schema("api-a", "1.0")
        eng.register_schema("api-b", "1.0")
        stats = eng.get_stats()
        assert stats["total_schemas"] == 2
        assert stats["unique_apis"] == 2

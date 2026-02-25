"""Tests for shieldops.topology.api_contract_validator."""

from __future__ import annotations

from shieldops.topology.api_contract_validator import (
    APIContract,
    APIContractValidator,
    BreakingChangeType,
    ContractReport,
    ContractStatus,
    ContractViolation,
    SchemaFormat,
)


def _engine(**kw) -> APIContractValidator:
    return APIContractValidator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ContractStatus (5 values)

    def test_status_valid(self):
        assert ContractStatus.VALID == "valid"

    def test_status_breaking_change(self):
        assert ContractStatus.BREAKING_CHANGE == "breaking_change"

    def test_status_deprecated_field(self):
        assert ContractStatus.DEPRECATED_FIELD == "deprecated_field"

    def test_status_missing_field(self):
        assert ContractStatus.MISSING_FIELD == "missing_field"

    def test_status_version_mismatch(self):
        assert ContractStatus.VERSION_MISMATCH == "version_mismatch"

    # BreakingChangeType (5 values)

    def test_change_field_removed(self):
        assert BreakingChangeType.FIELD_REMOVED == "field_removed"

    def test_change_type_changed(self):
        assert BreakingChangeType.TYPE_CHANGED == "type_changed"

    def test_change_required_added(self):
        assert BreakingChangeType.REQUIRED_ADDED == "required_added"

    def test_change_endpoint_removed(self):
        assert BreakingChangeType.ENDPOINT_REMOVED == "endpoint_removed"

    def test_change_response_changed(self):
        assert BreakingChangeType.RESPONSE_CHANGED == "response_changed"

    # SchemaFormat (5 values)

    def test_format_openapi(self):
        assert SchemaFormat.OPENAPI == "openapi"

    def test_format_protobuf(self):
        assert SchemaFormat.PROTOBUF == "protobuf"

    def test_format_graphql(self):
        assert SchemaFormat.GRAPHQL == "graphql"

    def test_format_avro(self):
        assert SchemaFormat.AVRO == "avro"

    def test_format_json_schema(self):
        assert SchemaFormat.JSON_SCHEMA == "json_schema"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_api_contract_defaults(self):
        c = APIContract()
        assert c.id
        assert c.provider_service == ""
        assert c.consumer_service == ""
        assert c.endpoint == ""
        assert c.schema_format == SchemaFormat.OPENAPI
        assert c.version == ""
        assert c.status == ContractStatus.VALID
        assert c.fields == []
        assert c.breaking_changes == []
        assert c.created_at > 0

    def test_contract_violation_defaults(self):
        v = ContractViolation()
        assert v.id
        assert v.contract_id == ""
        assert v.change_type == BreakingChangeType.FIELD_REMOVED
        assert v.field_name == ""
        assert v.old_value == ""
        assert v.new_value == ""
        assert v.is_breaking is False
        assert v.created_at > 0

    def test_contract_report_defaults(self):
        r = ContractReport()
        assert r.total_contracts == 0
        assert r.total_violations == 0
        assert r.compliance_pct == 0.0
        assert r.by_status == {}
        assert r.by_format == {}
        assert r.by_change_type == {}
        assert r.breaking_contracts == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# register_contract
# -------------------------------------------------------------------


class TestRegisterContract:
    def test_basic_register(self):
        eng = _engine()
        c = eng.register_contract("provider-a", "consumer-b")
        assert c.provider_service == "provider-a"
        assert c.consumer_service == "consumer-b"
        assert len(eng.list_contracts()) == 1

    def test_register_assigns_unique_ids(self):
        eng = _engine()
        c1 = eng.register_contract("p-a")
        c2 = eng.register_contract("p-b")
        assert c1.id != c2.id

    def test_register_with_fields(self):
        eng = _engine()
        c = eng.register_contract(
            "p-a",
            "c-b",
            endpoint="/api/v1/users",
            version="1.0.0",
            fields=["id", "name", "email"],
        )
        assert c.endpoint == "/api/v1/users"
        assert c.version == "1.0.0"
        assert len(c.fields) == 3

    def test_eviction_at_max(self):
        eng = _engine(max_contracts=3)
        ids = []
        for i in range(4):
            c = eng.register_contract(f"p-{i}")
            ids.append(c.id)
        contracts = eng.list_contracts(limit=100)
        assert len(contracts) == 3
        found = {c.id for c in contracts}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_contract
# -------------------------------------------------------------------


class TestGetContract:
    def test_get_existing(self):
        eng = _engine()
        c = eng.register_contract("p-a")
        found = eng.get_contract(c.id)
        assert found is not None
        assert found.id == c.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_contract("nonexistent") is None


# -------------------------------------------------------------------
# list_contracts
# -------------------------------------------------------------------


class TestListContracts:
    def test_list_all(self):
        eng = _engine()
        eng.register_contract("p-a")
        eng.register_contract("p-b")
        eng.register_contract("p-c")
        assert len(eng.list_contracts()) == 3

    def test_filter_by_provider(self):
        eng = _engine()
        eng.register_contract("p-a", "c-1")
        eng.register_contract("p-b", "c-2")
        eng.register_contract("p-a", "c-3")
        results = eng.list_contracts(provider="p-a")
        assert len(results) == 2

    def test_filter_by_consumer(self):
        eng = _engine()
        eng.register_contract("p-a", "c-1")
        eng.register_contract("p-b", "c-1")
        eng.register_contract("p-c", "c-2")
        results = eng.list_contracts(consumer="c-1")
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.register_contract(f"p-{i}")
        results = eng.list_contracts(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# validate_contract
# -------------------------------------------------------------------


class TestValidateContract:
    def test_valid_contract(self):
        eng = _engine()
        c = eng.register_contract(
            "p-a",
            "c-b",
            endpoint="/api/v1/users",
            version="1.0.0",
            fields=["id", "name"],
        )
        result = eng.validate_contract(c.id)
        assert result is not None
        assert result["is_valid"] is True
        assert result["status"] == "valid"

    def test_invalid_contract(self):
        eng = _engine()
        c = eng.register_contract("p-a")
        result = eng.validate_contract(c.id)
        assert result is not None
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0

    def test_validate_not_found(self):
        eng = _engine()
        assert eng.validate_contract("nope") is None


# -------------------------------------------------------------------
# detect_breaking_changes
# -------------------------------------------------------------------


class TestDetectBreakingChanges:
    def test_breaking_detected(self):
        eng = _engine()
        c = eng.register_contract(
            "p-a",
            fields=["id", "name", "email"],
        )
        violations = eng.detect_breaking_changes(
            c.id,
            ["id", "name"],
        )
        assert len(violations) == 1
        assert violations[0].field_name == "email"
        assert violations[0].is_breaking is True

    def test_no_breaking(self):
        eng = _engine()
        c = eng.register_contract(
            "p-a",
            fields=["id", "name"],
        )
        violations = eng.detect_breaking_changes(
            c.id,
            ["id", "name", "extra"],
        )
        assert violations == []

    def test_breaking_not_found(self):
        eng = _engine()
        violations = eng.detect_breaking_changes(
            "nope",
            ["a"],
        )
        assert violations == []

    def test_breaking_updates_status(self):
        eng = _engine()
        c = eng.register_contract(
            "p-a",
            fields=["id", "name"],
        )
        eng.detect_breaking_changes(c.id, ["id"])
        updated = eng.get_contract(c.id)
        assert updated is not None
        assert updated.status == ContractStatus.BREAKING_CHANGE


# -------------------------------------------------------------------
# check_version_compatibility
# -------------------------------------------------------------------


class TestCheckVersionCompatibility:
    def test_mismatch_detected(self):
        eng = _engine()
        eng.register_contract(
            "p-a",
            version="1.0.0",
        )
        eng.register_contract(
            "p-a",
            version="2.0.0",
        )
        issues = eng.check_version_compatibility()
        assert len(issues) == 1
        assert issues[0]["provider"] == "p-a"

    def test_no_mismatch(self):
        eng = _engine()
        eng.register_contract(
            "p-a",
            version="1.0.0",
        )
        eng.register_contract(
            "p-b",
            version="1.0.0",
        )
        issues = eng.check_version_compatibility()
        assert issues == []


# -------------------------------------------------------------------
# identify_undocumented_apis
# -------------------------------------------------------------------


class TestIdentifyUndocumentedApis:
    def test_undocumented_found(self):
        eng = _engine()
        eng.register_contract("p-a")
        undoc = eng.identify_undocumented_apis()
        assert len(undoc) == 1
        assert "endpoint" in undoc[0]["missing"]

    def test_all_documented(self):
        eng = _engine()
        eng.register_contract(
            "p-a",
            endpoint="/api",
            version="1.0",
            fields=["id"],
        )
        undoc = eng.identify_undocumented_apis()
        assert undoc == []


# -------------------------------------------------------------------
# calculate_compliance_rate
# -------------------------------------------------------------------


class TestCalculateComplianceRate:
    def test_empty(self):
        eng = _engine()
        assert eng.calculate_compliance_rate() == 100.0

    def test_all_valid(self):
        eng = _engine()
        eng.register_contract("p-a")
        eng.register_contract("p-b")
        assert eng.calculate_compliance_rate() == 100.0

    def test_with_breaking(self):
        eng = _engine()
        c = eng.register_contract(
            "p-a",
            fields=["id", "name"],
        )
        eng.register_contract("p-b")
        eng.detect_breaking_changes(c.id, ["id"])
        rate = eng.calculate_compliance_rate()
        assert rate == 50.0


# -------------------------------------------------------------------
# generate_contract_report
# -------------------------------------------------------------------


class TestGenerateContractReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_contract(
            "p-a",
            endpoint="/api",
            version="1.0",
            fields=["id"],
        )
        c = eng.register_contract(
            "p-b",
            fields=["x", "y"],
        )
        eng.detect_breaking_changes(c.id, ["x"])
        report = eng.generate_contract_report()
        assert report.total_contracts == 2
        assert report.total_violations == 1
        assert isinstance(report.by_status, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_contract_report()
        assert report.total_contracts == 0
        assert report.total_violations == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.register_contract("p-a")
        eng.register_contract("p-b")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_contracts()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_contracts"] == 0
        assert stats["total_violations"] == 0
        assert stats["compliance_target_pct"] == 95.0
        assert stats["status_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.register_contract("p-a")
        eng.register_contract("p-b")
        stats = eng.get_stats()
        assert stats["total_contracts"] == 2
        assert len(stats["status_distribution"]) > 0

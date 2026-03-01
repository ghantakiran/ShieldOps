"""Tests for shieldops.operations.config_drift_monitor — ConfigDriftMonitor."""

from __future__ import annotations

from shieldops.operations.config_drift_monitor import (
    ConfigDriftMonitor,
    ConfigDriftReport,
    DriftRecord,
    DriftResolution,
    DriftSeverity,
    DriftSource,
    DriftType,
)


def _engine(**kw) -> ConfigDriftMonitor:
    return ConfigDriftMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DriftType (5)
    def test_type_parameter_change(self):
        assert DriftType.PARAMETER_CHANGE == "parameter_change"

    def test_type_version_mismatch(self):
        assert DriftType.VERSION_MISMATCH == "version_mismatch"

    def test_type_missing_config(self):
        assert DriftType.MISSING_CONFIG == "missing_config"

    def test_type_extra_config(self):
        assert DriftType.EXTRA_CONFIG == "extra_config"

    def test_type_schema_violation(self):
        assert DriftType.SCHEMA_VIOLATION == "schema_violation"

    # DriftSeverity (5)
    def test_severity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert DriftSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert DriftSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert DriftSeverity.LOW == "low"

    def test_severity_informational(self):
        assert DriftSeverity.INFORMATIONAL == "informational"

    # DriftSource (5)
    def test_source_manual_change(self):
        assert DriftSource.MANUAL_CHANGE == "manual_change"

    def test_source_automation_bug(self):
        assert DriftSource.AUTOMATION_BUG == "automation_bug"

    def test_source_environment_sync(self):
        assert DriftSource.ENVIRONMENT_SYNC == "environment_sync"

    def test_source_upgrade_side_effect(self):
        assert DriftSource.UPGRADE_SIDE_EFFECT == "upgrade_side_effect"

    def test_source_unknown(self):
        assert DriftSource.UNKNOWN == "unknown"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_drift_record_defaults(self):
        r = DriftRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.drift_type == DriftType.PARAMETER_CHANGE
        assert r.severity == DriftSeverity.MODERATE
        assert r.source == DriftSource.UNKNOWN
        assert r.expected_value == ""
        assert r.actual_value == ""
        assert r.environment == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_drift_resolution_defaults(self):
        r = DriftResolution()
        assert r.id
        assert r.drift_id == ""
        assert r.resolved_by == ""
        assert r.resolution_method == ""
        assert r.resolution_time_minutes == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ConfigDriftReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_resolutions == 0
        assert r.by_drift_type == {}
        assert r.by_severity == {}
        assert r.by_source == {}
        assert r.unresolved_count == 0
        assert r.avg_resolution_time == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_drift
# -------------------------------------------------------------------


class TestRecordDrift:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drift("res-1")
        assert r.resource_id == "res-1"
        assert r.drift_type == DriftType.PARAMETER_CHANGE

    def test_with_params(self):
        eng = _engine()
        r = eng.record_drift(
            "res-2",
            drift_type=DriftType.VERSION_MISMATCH,
            severity=DriftSeverity.CRITICAL,
            source=DriftSource.MANUAL_CHANGE,
            expected_value="v1.0",
            actual_value="v1.2",
            environment="production",
            team="infra",
        )
        assert r.drift_type == DriftType.VERSION_MISMATCH
        assert r.severity == DriftSeverity.CRITICAL
        assert r.expected_value == "v1.0"
        assert r.environment == "production"

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_drift("res-a")
        r2 = eng.record_drift("res-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(f"res-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_drift
# -------------------------------------------------------------------


class TestGetDrift:
    def test_found(self):
        eng = _engine()
        r = eng.record_drift("res-x")
        assert eng.get_drift(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_drift("nonexistent") is None


# -------------------------------------------------------------------
# list_drifts
# -------------------------------------------------------------------


class TestListDrifts:
    def test_list_all(self):
        eng = _engine()
        eng.record_drift("res-a")
        eng.record_drift("res-b")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_drift(
            "res-a",
            drift_type=DriftType.MISSING_CONFIG,
        )
        eng.record_drift(
            "res-b",
            drift_type=DriftType.EXTRA_CONFIG,
        )
        results = eng.list_drifts(drift_type=DriftType.MISSING_CONFIG)
        assert len(results) == 1
        assert results[0].drift_type == DriftType.MISSING_CONFIG

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_drift(
            "res-a",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "res-b",
            severity=DriftSeverity.LOW,
        )
        results = eng.list_drifts(severity=DriftSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_environment(self):
        eng = _engine()
        eng.record_drift("res-a", environment="prod")
        eng.record_drift("res-b", environment="staging")
        results = eng.list_drifts(environment="prod")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_drift(f"res-{i}")
        assert len(eng.list_drifts(limit=5)) == 5


# -------------------------------------------------------------------
# add_resolution
# -------------------------------------------------------------------


class TestAddResolution:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drift("res-a")
        res = eng.add_resolution(r.id, "alice", "rollback", 15.0)
        assert res.drift_id == r.id
        assert res.resolved_by == "alice"
        assert res.resolution_method == "rollback"
        assert res.resolution_time_minutes == 15.0

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.add_resolution("d1", "alice", "fix", 5.0)
        r2 = eng.add_resolution("d2", "bob", "patch", 10.0)
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_resolution(f"d-{i}", "user", "fix", 5.0)
        assert len(eng._resolutions) == 2


# -------------------------------------------------------------------
# analyze_drift_by_environment
# -------------------------------------------------------------------


class TestAnalyzeDriftByEnvironment:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_drift_by_environment()
        assert result["total_environments"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        eng.record_drift(
            "res-a",
            environment="prod",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "res-b",
            environment="prod",
            severity=DriftSeverity.LOW,
        )
        eng.record_drift(
            "res-c",
            environment="staging",
        )
        result = eng.analyze_drift_by_environment()
        assert result["total_environments"] == 2
        prod = next(b for b in result["breakdown"] if b["environment"] == "prod")
        assert prod["total_drifts"] == 2
        assert prod["critical_count"] == 1


# -------------------------------------------------------------------
# identify_critical_drifts
# -------------------------------------------------------------------


class TestIdentifyCriticalDrifts:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_drifts() == []

    def test_only_critical_and_high(self):
        eng = _engine()
        eng.record_drift(
            "res-a",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "res-b",
            severity=DriftSeverity.HIGH,
        )
        eng.record_drift(
            "res-c",
            severity=DriftSeverity.LOW,
        )
        results = eng.identify_critical_drifts()
        assert len(results) == 2


# -------------------------------------------------------------------
# rank_by_severity
# -------------------------------------------------------------------


class TestRankBySeverity:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []

    def test_sorted_descending(self):
        eng = _engine()
        eng.record_drift(
            "res-a",
            severity=DriftSeverity.LOW,
        )
        eng.record_drift(
            "res-b",
            severity=DriftSeverity.CRITICAL,
        )
        results = eng.rank_by_severity()
        assert results[0]["severity"] == "critical"
        assert results[0]["severity_score"] >= results[-1]["severity_score"]


# -------------------------------------------------------------------
# detect_drift_trends
# -------------------------------------------------------------------


class TestDetectDriftTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_drift("res-a")
        result = eng.detect_drift_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_drift("res-a")
        result = eng.detect_drift_trends()
        assert result["trend"] in (
            "stable",
            "improving",
            "worsening",
        )

    def test_total_records_in_result(self):
        eng = _engine()
        for _ in range(6):
            eng.record_drift("res-a")
        result = eng.detect_drift_trends()
        assert result["total_records"] == 6


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, ConfigDriftReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        r = eng.record_drift(
            "res-a",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "res-b",
            severity=DriftSeverity.LOW,
        )
        eng.add_resolution(r.id, "alice", "fix", 30.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_resolutions == 1
        assert report.unresolved_count == 1
        assert report.avg_resolution_time == 30.0
        assert report.by_severity


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_resolutions(self):
        eng = _engine()
        eng.record_drift("res-a")
        eng.add_resolution("d1", "alice", "fix", 5.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._resolutions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_resolutions"] == 0
        assert stats["drift_type_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_drift_count=15.0)
        eng.record_drift(
            "res-a",
            drift_type=DriftType.PARAMETER_CHANGE,
        )
        eng.record_drift(
            "res-b",
            drift_type=DriftType.MISSING_CONFIG,
        )
        eng.add_resolution("d1", "alice", "fix", 5.0)
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_resolutions"] == 1
        assert stats["max_drift_count"] == 15.0
        assert stats["unique_resources"] == 2

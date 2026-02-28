"""Tests for shieldops.config.drift_analyzer."""

from __future__ import annotations

from shieldops.config.drift_analyzer import (
    ConfigDriftAnalyzer,
    DriftAnalyzerReport,
    DriftRecord,
    DriftRule,
    DriftSeverity,
    DriftSource,
    DriftType,
)


def _engine(**kw) -> ConfigDriftAnalyzer:
    return ConfigDriftAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DriftType (5)
    def test_type_value_change(self):
        assert DriftType.VALUE_CHANGE == "value_change"

    def test_type_missing_key(self):
        assert DriftType.MISSING_KEY == "missing_key"

    def test_type_extra_key(self):
        assert DriftType.EXTRA_KEY == "extra_key"

    def test_type_type_mismatch(self):
        assert DriftType.TYPE_MISMATCH == "type_mismatch"

    def test_type_format_change(self):
        assert DriftType.FORMAT_CHANGE == "format_change"

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
    def test_source_manual_edit(self):
        assert DriftSource.MANUAL_EDIT == "manual_edit"

    def test_source_deployment(self):
        assert DriftSource.DEPLOYMENT == "deployment"

    def test_source_hotfix(self):
        assert DriftSource.HOTFIX == "hotfix"

    def test_source_migration(self):
        assert DriftSource.MIGRATION == "migration"

    def test_source_unknown(self):
        assert DriftSource.UNKNOWN == "unknown"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_drift_record_defaults(self):
        r = DriftRecord()
        assert r.id
        assert r.config_name == ""
        assert r.drift_type == DriftType.VALUE_CHANGE
        assert r.severity == DriftSeverity.MODERATE
        assert r.source == DriftSource.UNKNOWN
        assert r.deviation_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_drift_rule_defaults(self):
        r = DriftRule()
        assert r.id
        assert r.rule_name == ""
        assert r.drift_type == DriftType.VALUE_CHANGE
        assert r.severity == DriftSeverity.MODERATE
        assert r.max_deviation_pct == 5.0
        assert r.auto_remediate is False
        assert r.created_at > 0

    def test_drift_report_defaults(self):
        r = DriftAnalyzerReport()
        assert r.total_drifts == 0
        assert r.total_rules == 0
        assert r.clean_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.critical_drift_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_drift
# -------------------------------------------------------------------


class TestRecordDrift:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drift(
            "db-config",
            drift_type=DriftType.VALUE_CHANGE,
            severity=DriftSeverity.HIGH,
        )
        assert r.config_name == "db-config"
        assert r.drift_type == DriftType.VALUE_CHANGE

    def test_with_source(self):
        eng = _engine()
        r = eng.record_drift(
            "app-config",
            source=DriftSource.HOTFIX,
        )
        assert r.source == DriftSource.HOTFIX

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(f"cfg-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_drift
# -------------------------------------------------------------------


class TestGetDrift:
    def test_found(self):
        eng = _engine()
        r = eng.record_drift("db-config")
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
        eng.record_drift("cfg-a")
        eng.record_drift("cfg-b")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_config(self):
        eng = _engine()
        eng.record_drift("cfg-a")
        eng.record_drift("cfg-b")
        results = eng.list_drifts(config_name="cfg-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_drift(
            "cfg-a",
            drift_type=DriftType.MISSING_KEY,
        )
        eng.record_drift(
            "cfg-b",
            drift_type=DriftType.EXTRA_KEY,
        )
        results = eng.list_drifts(drift_type=DriftType.MISSING_KEY)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            "strict-drift",
            drift_type=DriftType.VALUE_CHANGE,
            severity=DriftSeverity.CRITICAL,
            max_deviation_pct=2.0,
            auto_remediate=True,
        )
        assert p.rule_name == "strict-drift"
        assert p.max_deviation_pct == 2.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_drift_status
# -------------------------------------------------------------------


class TestAnalyzeDriftStatus:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.LOW,
            deviation_pct=2.0,
        )
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.HIGH,
            deviation_pct=8.0,
        )
        result = eng.analyze_drift_status("cfg-a")
        assert result["config_name"] == "cfg-a"
        assert result["drift_count"] == 2
        assert result["clean_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_drift_status("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_deviation_pct=10.0)
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.LOW,
            deviation_pct=3.0,
        )
        result = eng.analyze_drift_status("cfg-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_critical_drifts
# -------------------------------------------------------------------


class TestIdentifyCriticalDrifts:
    def test_with_criticals(self):
        eng = _engine()
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "cfg-b",
            severity=DriftSeverity.LOW,
        )
        results = eng.identify_critical_drifts()
        assert len(results) == 1
        assert results[0]["config_name"] == "cfg-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_drifts() == []


# -------------------------------------------------------------------
# rank_by_deviation
# -------------------------------------------------------------------


class TestRankByDeviation:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift("cfg-a", deviation_pct=10.0)
        eng.record_drift("cfg-a", deviation_pct=10.0)
        eng.record_drift("cfg-b", deviation_pct=1.0)
        results = eng.rank_by_deviation()
        assert results[0]["config_name"] == "cfg-a"
        assert results[0]["avg_deviation_pct"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_deviation() == []


# -------------------------------------------------------------------
# detect_drift_patterns
# -------------------------------------------------------------------


class TestDetectDriftPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_drift(
                "cfg-a",
                severity=DriftSeverity.CRITICAL,
            )
        eng.record_drift(
            "cfg-b",
            severity=DriftSeverity.LOW,
        )
        results = eng.detect_drift_patterns()
        assert len(results) == 1
        assert results[0]["config_name"] == "cfg-a"
        assert results[0]["pattern_detected"] is True

    def test_no_patterns(self):
        eng = _engine()
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.HIGH,
        )
        assert eng.detect_drift_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift(
            "cfg-a",
            severity=DriftSeverity.LOW,
        )
        eng.record_drift(
            "cfg-b",
            severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            "cfg-b",
            severity=DriftSeverity.CRITICAL,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_drifts == 3
        assert report.total_rules == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_drifts == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_drift("cfg-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_drifts"] == 0
        assert stats["total_rules"] == 0
        assert stats["drift_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_drift(
            "cfg-a",
            drift_type=DriftType.VALUE_CHANGE,
        )
        eng.record_drift(
            "cfg-b",
            drift_type=DriftType.MISSING_KEY,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_drifts"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_configs"] == 2

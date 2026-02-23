"""Tests for the configuration drift detector module.

Covers:
- DriftSeverity enum values, auto-classification (security=critical, log=info)
- DriftStatus enum values
- ConfigSnapshot model defaults
- DriftItem model defaults
- DriftReport model defaults
- ConfigDriftDetector creation
- take_snapshot() basic, max per env trimming
- set_baseline() basic
- detect_drift() between two envs, no drift, all different, missing keys
- detect_drift_from_baseline() basic, no baseline returns None
- acknowledge_drift() found and not found
- resolve_drift() found and not found
- list_reports() with limit
- get_report() found and not found
- get_stats() counts
"""

from __future__ import annotations

import pytest

from shieldops.observability.drift_detector import (
    ConfigDriftDetector,
    ConfigSnapshot,
    DriftItem,
    DriftReport,
    DriftSeverity,
    DriftStatus,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def detector() -> ConfigDriftDetector:
    """Return a fresh ConfigDriftDetector."""
    return ConfigDriftDetector()


@pytest.fixture()
def populated_detector() -> ConfigDriftDetector:
    """Return a detector with snapshots in two environments."""
    d = ConfigDriftDetector()
    d.take_snapshot(
        environment="production",
        config={"db_host": "prod-db", "log_level": "warn", "replicas": 3},
        service="api",
    )
    d.take_snapshot(
        environment="staging",
        config={"db_host": "stage-db", "log_level": "debug", "replicas": 1},
        service="api",
    )
    return d


# ── Enum Tests ───────────────────────────────────────────────────


class TestDriftSeverityEnum:
    def test_info_value(self) -> None:
        assert DriftSeverity.INFO == "info"

    def test_warning_value(self) -> None:
        assert DriftSeverity.WARNING == "warning"

    def test_critical_value(self) -> None:
        assert DriftSeverity.CRITICAL == "critical"

    def test_all_members(self) -> None:
        members = {m.value for m in DriftSeverity}
        assert members == {"info", "warning", "critical"}


class TestDriftStatusEnum:
    def test_detected_value(self) -> None:
        assert DriftStatus.DETECTED == "detected"

    def test_acknowledged_value(self) -> None:
        assert DriftStatus.ACKNOWLEDGED == "acknowledged"

    def test_resolved_value(self) -> None:
        assert DriftStatus.RESOLVED == "resolved"

    def test_ignored_value(self) -> None:
        assert DriftStatus.IGNORED == "ignored"

    def test_all_members(self) -> None:
        members = {m.value for m in DriftStatus}
        assert members == {"detected", "acknowledged", "resolved", "ignored"}


# ── Model Tests ──────────────────────────────────────────────────


class TestConfigSnapshotModel:
    def test_defaults(self) -> None:
        snap = ConfigSnapshot(environment="prod")
        assert snap.environment == "prod"
        assert snap.service == ""
        assert snap.config == {}
        assert snap.taken_at > 0
        assert snap.taken_by == ""
        assert snap.metadata == {}
        assert len(snap.id) == 12

    def test_unique_ids(self) -> None:
        s1 = ConfigSnapshot(environment="prod")
        s2 = ConfigSnapshot(environment="staging")
        assert s1.id != s2.id


class TestDriftItemModel:
    def test_defaults(self) -> None:
        item = DriftItem(key="db_host")
        assert item.key == "db_host"
        assert item.expected_value is None
        assert item.actual_value is None
        assert item.severity == DriftSeverity.WARNING
        assert item.status == DriftStatus.DETECTED
        assert item.environment == ""
        assert item.service == ""
        assert len(item.id) == 12


class TestDriftReportModel:
    def test_defaults(self) -> None:
        report = DriftReport(source_environment="prod", target_environment="staging")
        assert report.source_environment == "prod"
        assert report.target_environment == "staging"
        assert report.service == ""
        assert report.drifts == []
        assert report.total_keys_compared == 0
        assert report.drift_count == 0
        assert report.created_at > 0
        assert report.metadata == {}
        assert len(report.id) == 12


# ── Detector Creation ────────────────────────────────────────────


class TestDetectorCreation:
    def test_default_params(self) -> None:
        d = ConfigDriftDetector()
        assert d._max_per_env == 100
        assert d._retention_seconds == 30 * 86400

    def test_custom_params(self) -> None:
        d = ConfigDriftDetector(max_snapshots_per_env=10, retention_days=7)
        assert d._max_per_env == 10
        assert d._retention_seconds == 7 * 86400

    def test_starts_empty(self) -> None:
        d = ConfigDriftDetector()
        assert len(d._snapshots) == 0
        assert len(d._baselines) == 0
        assert len(d._reports) == 0
        assert len(d._drift_items) == 0


# ── take_snapshot ────────────────────────────────────────────────


class TestTakeSnapshot:
    def test_basic(self, detector: ConfigDriftDetector) -> None:
        snap = detector.take_snapshot(
            environment="prod",
            config={"key": "value"},
            service="api",
            taken_by="admin",
        )
        assert isinstance(snap, ConfigSnapshot)
        assert snap.environment == "prod"
        assert snap.config == {"key": "value"}
        assert snap.service == "api"
        assert snap.taken_by == "admin"

    def test_stored_in_snapshots(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"a": 1}, service="api")
        key = "prod:api"
        assert key in detector._snapshots
        assert len(detector._snapshots[key]) == 1

    def test_multiple_snapshots_same_env(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"v": 1}, service="api")
        detector.take_snapshot(environment="prod", config={"v": 2}, service="api")
        key = "prod:api"
        assert len(detector._snapshots[key]) == 2

    def test_max_per_env_trimming(self) -> None:
        d = ConfigDriftDetector(max_snapshots_per_env=3)
        for i in range(5):
            d.take_snapshot(environment="prod", config={"v": i}, service="api")
        key = "prod:api"
        assert len(d._snapshots[key]) == 3
        # Should keep the latest 3
        configs = [s.config["v"] for s in d._snapshots[key]]
        assert configs == [2, 3, 4]

    def test_metadata_stored(self, detector: ConfigDriftDetector) -> None:
        snap = detector.take_snapshot(
            environment="prod",
            config={"a": 1},
            metadata={"source": "terraform"},
        )
        assert snap.metadata == {"source": "terraform"}

    def test_different_services_independent(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"a": 1}, service="api")
        detector.take_snapshot(environment="prod", config={"b": 2}, service="web")
        assert "prod:api" in detector._snapshots
        assert "prod:web" in detector._snapshots
        assert len(detector._snapshots["prod:api"]) == 1
        assert len(detector._snapshots["prod:web"]) == 1


# ── set_baseline ─────────────────────────────────────────────────


class TestSetBaseline:
    def test_basic(self, detector: ConfigDriftDetector) -> None:
        snap = detector.set_baseline(environment="prod", config={"key": "value"}, service="api")
        assert isinstance(snap, ConfigSnapshot)
        assert snap.config == {"key": "value"}

    def test_stored_in_baselines(self, detector: ConfigDriftDetector) -> None:
        detector.set_baseline(environment="prod", config={"a": 1}, service="api")
        assert "prod:api" in detector._baselines

    def test_overwrites_previous_baseline(self, detector: ConfigDriftDetector) -> None:
        detector.set_baseline(environment="prod", config={"v": 1}, service="api")
        detector.set_baseline(environment="prod", config={"v": 2}, service="api")
        baseline = detector._baselines["prod:api"]
        assert baseline.config == {"v": 2}

    def test_metadata_stored(self, detector: ConfigDriftDetector) -> None:
        snap = detector.set_baseline(
            environment="prod",
            config={"a": 1},
            metadata={"approved_by": "ops"},
        )
        assert snap.metadata == {"approved_by": "ops"}


# ── detect_drift ─────────────────────────────────────────────────


class TestDetectDrift:
    def test_between_two_envs(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        assert isinstance(report, DriftReport)
        assert report.source_environment == "production"
        assert report.target_environment == "staging"
        # db_host, log_level, replicas all differ
        assert report.drift_count == 3
        assert len(report.drifts) == 3
        assert report.total_keys_compared == 3

    def test_no_drift_identical_configs(self, detector: ConfigDriftDetector) -> None:
        config = {"host": "db", "port": 5432}
        detector.take_snapshot(environment="prod", config=config, service="api")
        detector.take_snapshot(environment="staging", config=config, service="api")
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drift_count == 0
        assert report.drifts == []

    def test_all_keys_different(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"a": 1, "b": 2}, service="svc")
        detector.take_snapshot(environment="staging", config={"a": 10, "b": 20}, service="svc")
        report = detector.detect_drift("prod", "staging", service="svc")
        assert report.drift_count == 2
        assert report.total_keys_compared == 2

    def test_missing_keys_in_target(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"a": 1, "b": 2, "c": 3}, service="svc")
        detector.take_snapshot(environment="staging", config={"a": 1}, service="svc")
        report = detector.detect_drift("prod", "staging", service="svc")
        # b and c are missing in target => 2 drifts
        assert report.drift_count == 2
        drift_keys = {d.key for d in report.drifts}
        assert "b" in drift_keys
        assert "c" in drift_keys

    def test_extra_keys_in_target(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"a": 1}, service="svc")
        detector.take_snapshot(
            environment="staging", config={"a": 1, "extra": "val"}, service="svc"
        )
        report = detector.detect_drift("prod", "staging", service="svc")
        assert report.drift_count == 1
        assert report.drifts[0].key == "extra"

    def test_no_snapshots_empty_drift(self, detector: ConfigDriftDetector) -> None:
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drift_count == 0

    def test_drift_items_stored(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        for drift in report.drifts:
            assert drift.id in populated_detector._drift_items

    def test_report_stored(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        assert report.id in populated_detector._reports

    def test_drift_item_values(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        db_drift = next(d for d in report.drifts if d.key == "db_host")
        assert db_drift.expected_value == "prod-db"
        assert db_drift.actual_value == "stage-db"
        assert db_drift.environment == "staging"
        assert db_drift.service == "api"


# ── Severity Auto-Classification ─────────────────────────────────


class TestSeverityAutoClassification:
    def test_security_prefix_is_critical(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(
            environment="prod",
            config={"security_tls": "1.3"},
            service="api",
        )
        detector.take_snapshot(
            environment="staging",
            config={"security_tls": "1.2"},
            service="api",
        )
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drifts[0].severity == DriftSeverity.CRITICAL

    def test_auth_prefix_is_critical(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"auth_method": "oauth"}, service="api")
        detector.take_snapshot(
            environment="staging", config={"auth_method": "basic"}, service="api"
        )
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drifts[0].severity == DriftSeverity.CRITICAL

    def test_log_prefix_is_info(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"log_level": "warn"}, service="api")
        detector.take_snapshot(environment="staging", config={"log_level": "debug"}, service="api")
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drifts[0].severity == DriftSeverity.INFO

    def test_debug_prefix_is_info(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"debug_mode": False}, service="api")
        detector.take_snapshot(environment="staging", config={"debug_mode": True}, service="api")
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drifts[0].severity == DriftSeverity.INFO

    def test_generic_key_is_warning(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"replicas": 3}, service="api")
        detector.take_snapshot(environment="staging", config={"replicas": 1}, service="api")
        report = detector.detect_drift("prod", "staging", service="api")
        assert report.drifts[0].severity == DriftSeverity.WARNING


# ── detect_drift_from_baseline ───────────────────────────────────


class TestDetectDriftFromBaseline:
    def test_basic(self, detector: ConfigDriftDetector) -> None:
        detector.set_baseline(
            environment="prod", config={"host": "db", "port": 5432}, service="api"
        )
        detector.take_snapshot(
            environment="prod", config={"host": "db", "port": 5433}, service="api"
        )
        report = detector.detect_drift_from_baseline("prod", service="api")
        assert report is not None
        assert report.drift_count == 1
        assert report.drifts[0].key == "port"
        assert report.source_environment == "baseline"
        assert report.target_environment == "prod"

    def test_no_baseline_returns_none(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"host": "db"}, service="api")
        result = detector.detect_drift_from_baseline("prod", service="api")
        assert result is None

    def test_no_snapshot_compares_baseline_to_empty(self, detector: ConfigDriftDetector) -> None:
        detector.set_baseline(environment="prod", config={"host": "db"}, service="api")
        report = detector.detect_drift_from_baseline("prod", service="api")
        assert report is not None
        assert report.drift_count == 1

    def test_no_drift_from_baseline(self, detector: ConfigDriftDetector) -> None:
        config = {"host": "db", "port": 5432}
        detector.set_baseline(environment="prod", config=config, service="api")
        detector.take_snapshot(environment="prod", config=config, service="api")
        report = detector.detect_drift_from_baseline("prod", service="api")
        assert report is not None
        assert report.drift_count == 0


# ── acknowledge_drift ────────────────────────────────────────────


class TestAcknowledgeDrift:
    def test_found(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        drift_id = report.drifts[0].id
        result = populated_detector.acknowledge_drift(drift_id)
        assert result is not None
        assert result.status == DriftStatus.ACKNOWLEDGED

    def test_not_found(self, detector: ConfigDriftDetector) -> None:
        result = detector.acknowledge_drift("nonexistent-id")
        assert result is None

    def test_persists_status(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        drift_id = report.drifts[0].id
        populated_detector.acknowledge_drift(drift_id)
        item = populated_detector._drift_items[drift_id]
        assert item.status == DriftStatus.ACKNOWLEDGED


# ── resolve_drift ────────────────────────────────────────────────


class TestResolveDrift:
    def test_found(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        drift_id = report.drifts[0].id
        result = populated_detector.resolve_drift(drift_id)
        assert result is not None
        assert result.status == DriftStatus.RESOLVED

    def test_not_found(self, detector: ConfigDriftDetector) -> None:
        result = detector.resolve_drift("nonexistent-id")
        assert result is None

    def test_persists_status(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        drift_id = report.drifts[0].id
        populated_detector.resolve_drift(drift_id)
        item = populated_detector._drift_items[drift_id]
        assert item.status == DriftStatus.RESOLVED


# ── list_reports ─────────────────────────────────────────────────


class TestListReports:
    def test_empty(self, detector: ConfigDriftDetector) -> None:
        assert detector.list_reports() == []

    def test_returns_reports(self, populated_detector: ConfigDriftDetector) -> None:
        populated_detector.detect_drift("production", "staging", service="api")
        reports = populated_detector.list_reports()
        assert len(reports) == 1

    def test_multiple_reports(self, populated_detector: ConfigDriftDetector) -> None:
        populated_detector.detect_drift("production", "staging", service="api")
        populated_detector.detect_drift("staging", "production", service="api")
        reports = populated_detector.list_reports()
        assert len(reports) == 2

    def test_limit(self, populated_detector: ConfigDriftDetector) -> None:
        populated_detector.detect_drift("production", "staging", service="api")
        populated_detector.detect_drift("staging", "production", service="api")
        reports = populated_detector.list_reports(limit=1)
        assert len(reports) == 1

    def test_sorted_by_created_at_desc(self, populated_detector: ConfigDriftDetector) -> None:
        populated_detector.detect_drift("production", "staging", service="api")
        populated_detector.detect_drift("staging", "production", service="api")
        reports = populated_detector.list_reports()
        for i in range(len(reports) - 1):
            assert reports[i].created_at >= reports[i + 1].created_at


# ── get_report ───────────────────────────────────────────────────


class TestGetReport:
    def test_found(self, populated_detector: ConfigDriftDetector) -> None:
        report = populated_detector.detect_drift("production", "staging", service="api")
        result = populated_detector.get_report(report.id)
        assert result is not None
        assert result.id == report.id

    def test_not_found(self, detector: ConfigDriftDetector) -> None:
        assert detector.get_report("nonexistent") is None


# ── get_stats ────────────────────────────────────────────────────


class TestGetStats:
    def test_empty(self, detector: ConfigDriftDetector) -> None:
        stats = detector.get_stats()
        assert stats["total_reports"] == 0
        assert stats["total_snapshots"] == 0
        assert stats["total_baselines"] == 0
        assert stats["total_drifts"] == 0
        assert stats["by_severity"] == {}

    def test_with_snapshots(self, detector: ConfigDriftDetector) -> None:
        detector.take_snapshot(environment="prod", config={"a": 1}, service="api")
        detector.take_snapshot(environment="staging", config={"a": 2}, service="api")
        stats = detector.get_stats()
        assert stats["total_snapshots"] == 2

    def test_with_baselines(self, detector: ConfigDriftDetector) -> None:
        detector.set_baseline(environment="prod", config={"a": 1}, service="api")
        stats = detector.get_stats()
        assert stats["total_baselines"] == 1

    def test_with_drifts(self, populated_detector: ConfigDriftDetector) -> None:
        populated_detector.detect_drift("production", "staging", service="api")
        stats = populated_detector.get_stats()
        assert stats["total_reports"] == 1
        assert stats["total_drifts"] == 3
        total_severity = sum(stats["by_severity"].values())
        assert total_severity == 3

    def test_by_severity_breakdown(self, populated_detector: ConfigDriftDetector) -> None:
        populated_detector.detect_drift("production", "staging", service="api")
        stats = populated_detector.get_stats()
        # db_host -> warning, log_level -> info, replicas -> warning
        assert stats["by_severity"]["warning"] == 2
        assert stats["by_severity"]["info"] == 1

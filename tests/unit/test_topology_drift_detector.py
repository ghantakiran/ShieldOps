"""Tests for shieldops.topology.topology_drift_detector — TopologyDriftDetector."""

from __future__ import annotations

from shieldops.topology.topology_drift_detector import (
    DriftAssessment,
    DriftOrigin,
    DriftRecord,
    DriftSeverity,
    DriftType,
    TopologyDriftDetector,
    TopologyDriftReport,
)


def _engine(**kw) -> TopologyDriftDetector:
    return TopologyDriftDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_service_mismatch(self):
        assert DriftType.SERVICE_MISMATCH == "service_mismatch"

    def test_type_config_divergence(self):
        assert DriftType.CONFIG_DIVERGENCE == "config_divergence"

    def test_type_version_skew(self):
        assert DriftType.VERSION_SKEW == "version_skew"

    def test_type_dependency_shift(self):
        assert DriftType.DEPENDENCY_SHIFT == "dependency_shift"

    def test_type_capacity_imbalance(self):
        assert DriftType.CAPACITY_IMBALANCE == "capacity_imbalance"

    def test_severity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert DriftSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert DriftSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert DriftSeverity.LOW == "low"

    def test_severity_cosmetic(self):
        assert DriftSeverity.COSMETIC == "cosmetic"

    def test_origin_manual_change(self):
        assert DriftOrigin.MANUAL_CHANGE == "manual_change"

    def test_origin_automation_failure(self):
        assert DriftOrigin.AUTOMATION_FAILURE == "automation_failure"

    def test_origin_scaling_event(self):
        assert DriftOrigin.SCALING_EVENT == "scaling_event"

    def test_origin_deployment(self):
        assert DriftOrigin.DEPLOYMENT == "deployment"

    def test_origin_unknown(self):
        assert DriftOrigin.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_drift_record_defaults(self):
        r = DriftRecord()
        assert r.id
        assert r.drift_id == ""
        assert r.drift_type == DriftType.SERVICE_MISMATCH
        assert r.drift_severity == DriftSeverity.LOW
        assert r.drift_origin == DriftOrigin.UNKNOWN
        assert r.drift_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_drift_assessment_defaults(self):
        a = DriftAssessment()
        assert a.id
        assert a.drift_id == ""
        assert a.drift_type == DriftType.SERVICE_MISMATCH
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_topology_drift_report_defaults(self):
        r = TopologyDriftReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.critical_drifts == 0
        assert r.avg_drift_score == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_origin == {}
        assert r.top_drifting == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_drift
# ---------------------------------------------------------------------------


class TestRecordDrift:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drift(
            drift_id="DRF-001",
            drift_type=DriftType.CONFIG_DIVERGENCE,
            drift_severity=DriftSeverity.CRITICAL,
            drift_origin=DriftOrigin.MANUAL_CHANGE,
            drift_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.drift_id == "DRF-001"
        assert r.drift_type == DriftType.CONFIG_DIVERGENCE
        assert r.drift_severity == DriftSeverity.CRITICAL
        assert r.drift_origin == DriftOrigin.MANUAL_CHANGE
        assert r.drift_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(drift_id=f"DRF-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_drift
# ---------------------------------------------------------------------------


class TestGetDrift:
    def test_found(self):
        eng = _engine()
        r = eng.record_drift(
            drift_id="DRF-001",
            drift_severity=DriftSeverity.CRITICAL,
        )
        result = eng.get_drift(r.id)
        assert result is not None
        assert result.drift_severity == DriftSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_drift("nonexistent") is None


# ---------------------------------------------------------------------------
# list_drifts
# ---------------------------------------------------------------------------


class TestListDrifts:
    def test_list_all(self):
        eng = _engine()
        eng.record_drift(drift_id="DRF-001")
        eng.record_drift(drift_id="DRF-002")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            drift_type=DriftType.CONFIG_DIVERGENCE,
        )
        eng.record_drift(
            drift_id="DRF-002",
            drift_type=DriftType.VERSION_SKEW,
        )
        results = eng.list_drifts(
            drift_type=DriftType.CONFIG_DIVERGENCE,
        )
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            drift_severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            drift_id="DRF-002",
            drift_severity=DriftSeverity.LOW,
        )
        results = eng.list_drifts(
            drift_severity=DriftSeverity.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_drift(drift_id="DRF-001", team="sre")
        eng.record_drift(drift_id="DRF-002", team="platform")
        results = eng.list_drifts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_drift(drift_id=f"DRF-{i}")
        assert len(eng.list_drifts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            drift_id="DRF-001",
            drift_type=DriftType.CONFIG_DIVERGENCE,
            assessment_score=75.0,
            threshold=50.0,
            breached=True,
            description="Config divergence detected",
        )
        assert a.drift_id == "DRF-001"
        assert a.drift_type == DriftType.CONFIG_DIVERGENCE
        assert a.assessment_score == 75.0
        assert a.threshold == 50.0
        assert a.breached is True
        assert a.description == "Config divergence detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(drift_id=f"DRF-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_drift_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDriftDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            drift_type=DriftType.CONFIG_DIVERGENCE,
            drift_score=80.0,
        )
        eng.record_drift(
            drift_id="DRF-002",
            drift_type=DriftType.CONFIG_DIVERGENCE,
            drift_score=60.0,
        )
        result = eng.analyze_drift_distribution()
        assert "config_divergence" in result
        assert result["config_divergence"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_drift_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_drifts
# ---------------------------------------------------------------------------


class TestIdentifyCriticalDrifts:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            drift_severity=DriftSeverity.CRITICAL,
        )
        eng.record_drift(
            drift_id="DRF-002",
            drift_severity=DriftSeverity.LOW,
        )
        results = eng.identify_critical_drifts()
        assert len(results) == 1
        assert results[0]["drift_id"] == "DRF-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_drift_score
# ---------------------------------------------------------------------------


class TestRankByDriftScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            service="api-gateway",
            drift_score=90.0,
        )
        eng.record_drift(
            drift_id="DRF-002",
            service="payments",
            drift_score=30.0,
        )
        results = eng.rank_by_drift_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_drift_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_drift_score() == []


# ---------------------------------------------------------------------------
# detect_drift_trends
# ---------------------------------------------------------------------------


class TestDetectDriftTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(
                drift_id="DRF-001",
                assessment_score=50.0,
            )
        result = eng.detect_drift_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(drift_id="DRF-001", assessment_score=30.0)
        eng.add_assessment(drift_id="DRF-002", assessment_score=30.0)
        eng.add_assessment(drift_id="DRF-003", assessment_score=80.0)
        eng.add_assessment(drift_id="DRF-004", assessment_score=80.0)
        result = eng.detect_drift_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_drift_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            drift_type=DriftType.CONFIG_DIVERGENCE,
            drift_severity=DriftSeverity.CRITICAL,
            drift_origin=DriftOrigin.MANUAL_CHANGE,
            drift_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TopologyDriftReport)
        assert report.total_records == 1
        assert report.critical_drifts == 1
        assert len(report.top_drifting) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_drift(drift_id="DRF-001")
        eng.add_assessment(drift_id="DRF-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_drift(
            drift_id="DRF-001",
            drift_type=DriftType.CONFIG_DIVERGENCE,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "config_divergence" in stats["type_distribution"]

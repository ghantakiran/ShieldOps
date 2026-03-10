"""Tests for PolicyDriftIntelligence."""

from __future__ import annotations

from shieldops.compliance.policy_drift_intelligence import (
    DriftSeverity,
    DriftSource,
    DriftType,
    PolicyDriftIntelligence,
)


def _engine(**kw) -> PolicyDriftIntelligence:
    return PolicyDriftIntelligence(**kw)


class TestEnums:
    def test_drift_type_values(self):
        assert DriftType.CONFIGURATION == "configuration"
        assert DriftType.PERMISSION == "permission"
        assert DriftType.NETWORK == "network"
        assert DriftType.ENCRYPTION == "encryption"

    def test_drift_severity_values(self):
        assert DriftSeverity.CRITICAL == "critical"
        assert DriftSeverity.HIGH == "high"
        assert DriftSeverity.MEDIUM == "medium"
        assert DriftSeverity.LOW == "low"

    def test_drift_source_values(self):
        assert DriftSource.MANUAL_CHANGE == "manual_change"
        assert DriftSource.DEPLOYMENT == "deployment"
        assert DriftSource.EXTERNAL == "external"
        assert DriftSource.UNKNOWN == "unknown"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="drift-001",
            drift_type=DriftType.PERMISSION,
            drift_severity=DriftSeverity.CRITICAL,
            score=30.0,
            service="iam",
            team="security",
        )
        assert r.name == "drift-001"
        assert r.drift_type == DriftType.PERMISSION
        assert r.score == 30.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestDetectPolicyDrift:
    def test_returns_sorted_by_risk(self):
        eng = _engine()
        eng.add_record(
            name="critical",
            drift_severity=DriftSeverity.CRITICAL,
            score=20.0,
        )
        eng.add_record(
            name="low",
            drift_severity=DriftSeverity.LOW,
            score=80.0,
        )
        results = eng.detect_policy_drift()
        assert results[0]["name"] == "critical"
        assert results[0]["drift_risk"] > results[1]["drift_risk"]

    def test_empty(self):
        eng = _engine()
        assert eng.detect_policy_drift() == []


class TestComputeDriftVelocity:
    def test_accelerating(self):
        eng = _engine(threshold=50.0)
        eng.add_record(name="a", score=80.0)
        eng.add_record(name="b", score=80.0)
        eng.add_record(name="c", score=20.0)
        eng.add_record(name="d", score=20.0)
        result = eng.compute_drift_velocity()
        assert result["trend"] == "accelerating"

    def test_insufficient_data(self):
        eng = _engine()
        eng.add_record(name="a", score=50.0)
        result = eng.compute_drift_velocity()
        assert result["reason"] == "insufficient_data"


class TestRecommendPolicyAlignment:
    def test_with_drifted_policies(self):
        eng = _engine(threshold=80.0)
        eng.add_record(
            name="a",
            drift_type=DriftType.PERMISSION,
            drift_severity=DriftSeverity.CRITICAL,
            score=30.0,
        )
        results = eng.recommend_policy_alignment()
        assert len(results) == 1
        assert results[0]["drift_type"] == "permission"
        assert results[0]["priority"] == "critical"

    def test_no_drift(self):
        eng = _engine(threshold=50.0)
        eng.add_record(name="ok", score=90.0)
        results = eng.recommend_policy_alignment()
        assert len(results) == 0

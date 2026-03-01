"""Tests for shieldops.changes.feature_flag_impact — FeatureFlagImpactTracker."""

from __future__ import annotations

from shieldops.changes.feature_flag_impact import (
    FeatureFlagImpactReport,
    FeatureFlagImpactTracker,
    FlagImpactRecord,
    FlagImpactType,
    FlagRisk,
    FlagStatus,
    ImpactMeasurement,
)


def _engine(**kw) -> FeatureFlagImpactTracker:
    return FeatureFlagImpactTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_impact_type_performance(self):
        assert FlagImpactType.PERFORMANCE == "performance"

    def test_impact_type_reliability(self):
        assert FlagImpactType.RELIABILITY == "reliability"

    def test_impact_type_error_rate(self):
        assert FlagImpactType.ERROR_RATE == "error_rate"

    def test_impact_type_latency(self):
        assert FlagImpactType.LATENCY == "latency"

    def test_impact_type_user_experience(self):
        assert FlagImpactType.USER_EXPERIENCE == "user_experience"

    def test_status_active(self):
        assert FlagStatus.ACTIVE == "active"

    def test_status_rolling_out(self):
        assert FlagStatus.ROLLING_OUT == "rolling_out"

    def test_status_stable(self):
        assert FlagStatus.STABLE == "stable"

    def test_status_degrading(self):
        assert FlagStatus.DEGRADING == "degrading"

    def test_status_disabled(self):
        assert FlagStatus.DISABLED == "disabled"

    def test_risk_high(self):
        assert FlagRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert FlagRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert FlagRisk.LOW == "low"

    def test_risk_minimal(self):
        assert FlagRisk.MINIMAL == "minimal"

    def test_risk_none(self):
        assert FlagRisk.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_flag_impact_record_defaults(self):
        r = FlagImpactRecord()
        assert r.id
        assert r.flag_id == ""
        assert r.flag_impact_type == FlagImpactType.PERFORMANCE
        assert r.flag_status == FlagStatus.ACTIVE
        assert r.flag_risk == FlagRisk.LOW
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_measurement_defaults(self):
        m = ImpactMeasurement()
        assert m.id
        assert m.flag_id == ""
        assert m.flag_impact_type == FlagImpactType.PERFORMANCE
        assert m.value == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_feature_flag_impact_report_defaults(self):
        r = FeatureFlagImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_measurements == 0
        assert r.negative_flags == 0
        assert r.avg_impact_score == 0.0
        assert r.by_impact_type == {}
        assert r.by_status == {}
        assert r.by_risk == {}
        assert r.top_impactful == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_impact
# ---------------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact(
            flag_id="FLAG-001",
            flag_impact_type=FlagImpactType.LATENCY,
            flag_status=FlagStatus.ROLLING_OUT,
            flag_risk=FlagRisk.MODERATE,
            impact_score=65.0,
            service="api-gateway",
            team="sre",
        )
        assert r.flag_id == "FLAG-001"
        assert r.flag_impact_type == FlagImpactType.LATENCY
        assert r.flag_status == FlagStatus.ROLLING_OUT
        assert r.flag_risk == FlagRisk.MODERATE
        assert r.impact_score == 65.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(flag_id=f"FLAG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact(
            flag_id="FLAG-001",
            flag_status=FlagStatus.DEGRADING,
        )
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.flag_status == FlagStatus.DEGRADING

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# ---------------------------------------------------------------------------
# list_impacts
# ---------------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact(flag_id="FLAG-001")
        eng.record_impact(flag_id="FLAG-002")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_impact_type(self):
        eng = _engine()
        eng.record_impact(
            flag_id="FLAG-001",
            flag_impact_type=FlagImpactType.LATENCY,
        )
        eng.record_impact(
            flag_id="FLAG-002",
            flag_impact_type=FlagImpactType.PERFORMANCE,
        )
        results = eng.list_impacts(impact_type=FlagImpactType.LATENCY)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_impact(
            flag_id="FLAG-001",
            flag_status=FlagStatus.DEGRADING,
        )
        eng.record_impact(
            flag_id="FLAG-002",
            flag_status=FlagStatus.ACTIVE,
        )
        results = eng.list_impacts(status=FlagStatus.DEGRADING)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_impact(flag_id="FLAG-001", service="api")
        eng.record_impact(flag_id="FLAG-002", service="web")
        results = eng.list_impacts(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_impact(flag_id="FLAG-001", team="sre")
        eng.record_impact(flag_id="FLAG-002", team="platform")
        results = eng.list_impacts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(flag_id=f"FLAG-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_measurement
# ---------------------------------------------------------------------------


class TestAddMeasurement:
    def test_basic(self):
        eng = _engine()
        m = eng.add_measurement(
            flag_id="FLAG-001",
            flag_impact_type=FlagImpactType.ERROR_RATE,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Error rate within limits",
        )
        assert m.flag_id == "FLAG-001"
        assert m.flag_impact_type == FlagImpactType.ERROR_RATE
        assert m.value == 75.0
        assert m.threshold == 80.0
        assert m.breached is False
        assert m.description == "Error rate within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_measurement(flag_id=f"FLAG-{i}")
        assert len(eng._measurements) == 2


# ---------------------------------------------------------------------------
# analyze_flag_performance
# ---------------------------------------------------------------------------


class TestAnalyzeFlagPerformance:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            flag_id="FLAG-001",
            flag_impact_type=FlagImpactType.PERFORMANCE,
            impact_score=70.0,
        )
        eng.record_impact(
            flag_id="FLAG-002",
            flag_impact_type=FlagImpactType.PERFORMANCE,
            impact_score=90.0,
        )
        result = eng.analyze_flag_performance()
        assert "performance" in result
        assert result["performance"]["count"] == 2
        assert result["performance"]["avg_impact_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_flag_performance() == {}


# ---------------------------------------------------------------------------
# identify_negative_flags
# ---------------------------------------------------------------------------


class TestIdentifyNegativeFlags:
    def test_detects_negative(self):
        eng = _engine()
        eng.record_impact(
            flag_id="FLAG-001",
            flag_status=FlagStatus.DEGRADING,
        )
        eng.record_impact(
            flag_id="FLAG-002",
            flag_status=FlagStatus.ACTIVE,
        )
        results = eng.identify_negative_flags()
        assert len(results) == 1
        assert results[0]["flag_id"] == "FLAG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_negative_flags() == []


# ---------------------------------------------------------------------------
# rank_by_impact_score
# ---------------------------------------------------------------------------


class TestRankByImpactScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_impact(flag_id="FLAG-001", service="api", impact_score=90.0)
        eng.record_impact(flag_id="FLAG-002", service="api", impact_score=80.0)
        eng.record_impact(flag_id="FLAG-003", service="web", impact_score=50.0)
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_impact_regressions
# ---------------------------------------------------------------------------


class TestDetectImpactRegressions:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_measurement(flag_id="FLAG-001", value=val)
        result = eng.detect_impact_regressions()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_measurement(flag_id="FLAG-001", value=val)
        result = eng.detect_impact_regressions()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_regressions()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            flag_id="FLAG-001",
            flag_impact_type=FlagImpactType.PERFORMANCE,
            flag_status=FlagStatus.DEGRADING,
            impact_score=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, FeatureFlagImpactReport)
        assert report.total_records == 1
        assert report.negative_flags == 1
        assert report.avg_impact_score == 50.0
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
        eng.record_impact(flag_id="FLAG-001")
        eng.add_measurement(flag_id="FLAG-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._measurements) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_measurements"] == 0
        assert stats["impact_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            flag_id="FLAG-001",
            flag_impact_type=FlagImpactType.LATENCY,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_flags"] == 1
        assert "latency" in stats["impact_type_distribution"]

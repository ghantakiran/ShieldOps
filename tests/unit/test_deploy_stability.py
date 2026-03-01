"""Tests for shieldops.changes.deploy_stability — DeploymentStabilityTracker."""

from __future__ import annotations

from shieldops.changes.deploy_stability import (
    DeploymentStabilityReport,
    DeploymentStabilityTracker,
    StabilityMeasurement,
    StabilityMetric,
    StabilityPhase,
    StabilityRecord,
    StabilityStatus,
)


def _engine(**kw) -> DeploymentStabilityTracker:
    return DeploymentStabilityTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_phase_immediate(self):
        assert StabilityPhase.IMMEDIATE == "immediate"

    def test_phase_short_term(self):
        assert StabilityPhase.SHORT_TERM == "short_term"

    def test_phase_medium_term(self):
        assert StabilityPhase.MEDIUM_TERM == "medium_term"

    def test_phase_long_term(self):
        assert StabilityPhase.LONG_TERM == "long_term"

    def test_phase_baseline(self):
        assert StabilityPhase.BASELINE == "baseline"

    def test_status_stable(self):
        assert StabilityStatus.STABLE == "stable"

    def test_status_minor_issues(self):
        assert StabilityStatus.MINOR_ISSUES == "minor_issues"

    def test_status_degraded(self):
        assert StabilityStatus.DEGRADED == "degraded"

    def test_status_unstable(self):
        assert StabilityStatus.UNSTABLE == "unstable"

    def test_status_rollback_needed(self):
        assert StabilityStatus.ROLLBACK_NEEDED == "rollback_needed"

    def test_metric_error_rate(self):
        assert StabilityMetric.ERROR_RATE == "error_rate"

    def test_metric_latency(self):
        assert StabilityMetric.LATENCY == "latency"

    def test_metric_cpu_usage(self):
        assert StabilityMetric.CPU_USAGE == "cpu_usage"

    def test_metric_memory_usage(self):
        assert StabilityMetric.MEMORY_USAGE == "memory_usage"

    def test_metric_request_rate(self):
        assert StabilityMetric.REQUEST_RATE == "request_rate"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_stability_record_defaults(self):
        r = StabilityRecord()
        assert r.id
        assert r.deployment_id == ""
        assert r.stability_phase == StabilityPhase.IMMEDIATE
        assert r.stability_status == StabilityStatus.STABLE
        assert r.stability_metric == StabilityMetric.ERROR_RATE
        assert r.stability_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_stability_measurement_defaults(self):
        m = StabilityMeasurement()
        assert m.id
        assert m.deployment_id == ""
        assert m.stability_metric == StabilityMetric.ERROR_RATE
        assert m.value == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_deployment_stability_report_defaults(self):
        r = DeploymentStabilityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_measurements == 0
        assert r.unstable_deployments == 0
        assert r.avg_stability_score == 0.0
        assert r.by_phase == {}
        assert r.by_status == {}
        assert r.by_metric == {}
        assert r.top_unstable == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_stability
# ---------------------------------------------------------------------------


class TestRecordStability:
    def test_basic(self):
        eng = _engine()
        r = eng.record_stability(
            deployment_id="DEP-001",
            stability_phase=StabilityPhase.SHORT_TERM,
            stability_status=StabilityStatus.DEGRADED,
            stability_metric=StabilityMetric.LATENCY,
            stability_score=65.0,
            service="api-gateway",
            team="sre",
        )
        assert r.deployment_id == "DEP-001"
        assert r.stability_phase == StabilityPhase.SHORT_TERM
        assert r.stability_status == StabilityStatus.DEGRADED
        assert r.stability_metric == StabilityMetric.LATENCY
        assert r.stability_score == 65.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_stability(deployment_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_stability
# ---------------------------------------------------------------------------


class TestGetStability:
    def test_found(self):
        eng = _engine()
        r = eng.record_stability(
            deployment_id="DEP-001",
            stability_status=StabilityStatus.UNSTABLE,
        )
        result = eng.get_stability(r.id)
        assert result is not None
        assert result.stability_status == StabilityStatus.UNSTABLE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_stability("nonexistent") is None


# ---------------------------------------------------------------------------
# list_stabilities
# ---------------------------------------------------------------------------


class TestListStabilities:
    def test_list_all(self):
        eng = _engine()
        eng.record_stability(deployment_id="DEP-001")
        eng.record_stability(deployment_id="DEP-002")
        assert len(eng.list_stabilities()) == 2

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_stability(
            deployment_id="DEP-001",
            stability_phase=StabilityPhase.LONG_TERM,
        )
        eng.record_stability(
            deployment_id="DEP-002",
            stability_phase=StabilityPhase.IMMEDIATE,
        )
        results = eng.list_stabilities(phase=StabilityPhase.LONG_TERM)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_stability(
            deployment_id="DEP-001",
            stability_status=StabilityStatus.UNSTABLE,
        )
        eng.record_stability(
            deployment_id="DEP-002",
            stability_status=StabilityStatus.STABLE,
        )
        results = eng.list_stabilities(status=StabilityStatus.UNSTABLE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_stability(deployment_id="DEP-001", service="api")
        eng.record_stability(deployment_id="DEP-002", service="web")
        results = eng.list_stabilities(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_stability(deployment_id="DEP-001", team="sre")
        eng.record_stability(deployment_id="DEP-002", team="platform")
        results = eng.list_stabilities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_stability(deployment_id=f"DEP-{i}")
        assert len(eng.list_stabilities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_measurement
# ---------------------------------------------------------------------------


class TestAddMeasurement:
    def test_basic(self):
        eng = _engine()
        m = eng.add_measurement(
            deployment_id="DEP-001",
            stability_metric=StabilityMetric.CPU_USAGE,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="CPU within limits",
        )
        assert m.deployment_id == "DEP-001"
        assert m.stability_metric == StabilityMetric.CPU_USAGE
        assert m.value == 75.0
        assert m.threshold == 80.0
        assert m.breached is False
        assert m.description == "CPU within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_measurement(deployment_id=f"DEP-{i}")
        assert len(eng._measurements) == 2


# ---------------------------------------------------------------------------
# analyze_stability_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeStabilityPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_stability(
            deployment_id="DEP-001",
            stability_phase=StabilityPhase.IMMEDIATE,
            stability_score=70.0,
        )
        eng.record_stability(
            deployment_id="DEP-002",
            stability_phase=StabilityPhase.IMMEDIATE,
            stability_score=90.0,
        )
        result = eng.analyze_stability_patterns()
        assert "immediate" in result
        assert result["immediate"]["count"] == 2
        assert result["immediate"]["avg_stability_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_stability_patterns() == {}


# ---------------------------------------------------------------------------
# identify_unstable_deployments
# ---------------------------------------------------------------------------


class TestIdentifyUnstableDeployments:
    def test_detects_unstable(self):
        eng = _engine()
        eng.record_stability(
            deployment_id="DEP-001",
            stability_status=StabilityStatus.UNSTABLE,
        )
        eng.record_stability(
            deployment_id="DEP-002",
            stability_status=StabilityStatus.STABLE,
        )
        results = eng.identify_unstable_deployments()
        assert len(results) == 1
        assert results[0]["deployment_id"] == "DEP-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unstable_deployments() == []


# ---------------------------------------------------------------------------
# rank_by_stability_score
# ---------------------------------------------------------------------------


class TestRankByStabilityScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_stability(deployment_id="DEP-001", service="api", stability_score=90.0)
        eng.record_stability(deployment_id="DEP-002", service="api", stability_score=80.0)
        eng.record_stability(deployment_id="DEP-003", service="web", stability_score=50.0)
        results = eng.rank_by_stability_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_stability_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_stability_score() == []


# ---------------------------------------------------------------------------
# detect_stability_trends
# ---------------------------------------------------------------------------


class TestDetectStabilityTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_measurement(deployment_id="DEP-001", value=val)
        result = eng.detect_stability_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_measurement(deployment_id="DEP-001", value=val)
        result = eng.detect_stability_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_stability_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_stability(
            deployment_id="DEP-001",
            stability_phase=StabilityPhase.IMMEDIATE,
            stability_status=StabilityStatus.UNSTABLE,
            stability_score=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DeploymentStabilityReport)
        assert report.total_records == 1
        assert report.unstable_deployments == 1
        assert report.avg_stability_score == 50.0
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
        eng.record_stability(deployment_id="DEP-001")
        eng.add_measurement(deployment_id="DEP-001")
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
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_stability(
            deployment_id="DEP-001",
            stability_phase=StabilityPhase.LONG_TERM,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_deployments"] == 1
        assert "long_term" in stats["phase_distribution"]

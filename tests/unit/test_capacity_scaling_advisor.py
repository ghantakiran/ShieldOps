"""Tests for shieldops.analytics.capacity_scaling_advisor — CapacityScalingAdvisor."""

from __future__ import annotations

from shieldops.analytics.capacity_scaling_advisor import (
    CapacityScalingAdvisor,
    CapacityScalingReport,
    ProvisioningStatus,
    ScalingAction,
    ScalingRecommendation,
    ScalingRecord,
    ScalingTrigger,
)


def _engine(**kw) -> CapacityScalingAdvisor:
    return CapacityScalingAdvisor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_action_scale_up(self):
        assert ScalingAction.SCALE_UP == "scale_up"

    def test_action_scale_down(self):
        assert ScalingAction.SCALE_DOWN == "scale_down"

    def test_action_scale_out(self):
        assert ScalingAction.SCALE_OUT == "scale_out"

    def test_action_scale_in(self):
        assert ScalingAction.SCALE_IN == "scale_in"

    def test_action_no_action(self):
        assert ScalingAction.NO_ACTION == "no_action"

    def test_status_over_provisioned(self):
        assert ProvisioningStatus.OVER_PROVISIONED == "over_provisioned"

    def test_status_right_sized(self):
        assert ProvisioningStatus.RIGHT_SIZED == "right_sized"

    def test_status_under_provisioned(self):
        assert ProvisioningStatus.UNDER_PROVISIONED == "under_provisioned"

    def test_status_critical(self):
        assert ProvisioningStatus.CRITICAL == "critical"

    def test_status_unknown(self):
        assert ProvisioningStatus.UNKNOWN == "unknown"

    def test_trigger_cpu(self):
        assert ScalingTrigger.CPU_THRESHOLD == "cpu_threshold"

    def test_trigger_memory(self):
        assert ScalingTrigger.MEMORY_THRESHOLD == "memory_threshold"

    def test_trigger_request_rate(self):
        assert ScalingTrigger.REQUEST_RATE == "request_rate"

    def test_trigger_schedule(self):
        assert ScalingTrigger.SCHEDULE == "schedule"

    def test_trigger_manual(self):
        assert ScalingTrigger.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_scaling_record_defaults(self):
        r = ScalingRecord()
        assert r.id
        assert r.scaling_id == ""
        assert r.scaling_action == ScalingAction.NO_ACTION
        assert r.provisioning_status == ProvisioningStatus.UNKNOWN
        assert r.scaling_trigger == ScalingTrigger.MANUAL
        assert r.efficiency_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_scaling_recommendation_defaults(self):
        r = ScalingRecommendation()
        assert r.id
        assert r.scaling_id == ""
        assert r.scaling_action == ScalingAction.NO_ACTION
        assert r.recommendation_score == 0.0
        assert r.threshold == 70.0
        assert r.breached is False
        assert r.description == ""
        assert r.created_at > 0

    def test_scaling_report_defaults(self):
        r = CapacityScalingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_recommendations == 0
        assert r.inefficient_count == 0
        assert r.avg_efficiency_score == 0.0
        assert r.by_action == {}
        assert r.by_status == {}
        assert r.by_trigger == {}
        assert r.top_inefficient == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_scaling
# ---------------------------------------------------------------------------


class TestRecordScaling:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scaling(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
            provisioning_status=ProvisioningStatus.UNDER_PROVISIONED,
            scaling_trigger=ScalingTrigger.CPU_THRESHOLD,
            efficiency_score=45.0,
            service="api-svc",
            team="sre",
        )
        assert r.scaling_id == "SCL-001"
        assert r.scaling_action == ScalingAction.SCALE_UP
        assert r.provisioning_status == ProvisioningStatus.UNDER_PROVISIONED
        assert r.scaling_trigger == ScalingTrigger.CPU_THRESHOLD
        assert r.efficiency_score == 45.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scaling(scaling_id=f"SCL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_scaling
# ---------------------------------------------------------------------------


class TestGetScaling:
    def test_found(self):
        eng = _engine()
        r = eng.record_scaling(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
        )
        result = eng.get_scaling(r.id)
        assert result is not None
        assert result.scaling_action == ScalingAction.SCALE_UP

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scaling("nonexistent") is None


# ---------------------------------------------------------------------------
# list_scalings
# ---------------------------------------------------------------------------


class TestListScalings:
    def test_list_all(self):
        eng = _engine()
        eng.record_scaling(scaling_id="SCL-001")
        eng.record_scaling(scaling_id="SCL-002")
        assert len(eng.list_scalings()) == 2

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_scaling(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
        )
        eng.record_scaling(
            scaling_id="SCL-002",
            scaling_action=ScalingAction.SCALE_DOWN,
        )
        results = eng.list_scalings(scaling_action=ScalingAction.SCALE_UP)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_scaling(
            scaling_id="SCL-001",
            provisioning_status=ProvisioningStatus.OVER_PROVISIONED,
        )
        eng.record_scaling(
            scaling_id="SCL-002",
            provisioning_status=ProvisioningStatus.RIGHT_SIZED,
        )
        results = eng.list_scalings(
            provisioning_status=ProvisioningStatus.OVER_PROVISIONED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_scaling(scaling_id="SCL-001", team="sre")
        eng.record_scaling(scaling_id="SCL-002", team="platform")
        results = eng.list_scalings(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_scaling(scaling_id=f"SCL-{i}")
        assert len(eng.list_scalings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_recommendation
# ---------------------------------------------------------------------------


class TestAddRecommendation:
    def test_basic(self):
        eng = _engine()
        r = eng.add_recommendation(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
            recommendation_score=50.0,
            threshold=70.0,
            description="Needs scaling",
        )
        assert r.scaling_id == "SCL-001"
        assert r.scaling_action == ScalingAction.SCALE_UP
        assert r.recommendation_score == 50.0
        assert r.breached is True

    def test_not_breached(self):
        eng = _engine()
        r = eng.add_recommendation(
            scaling_id="SCL-002",
            recommendation_score=80.0,
            threshold=70.0,
        )
        assert r.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_recommendation(scaling_id=f"SCL-{i}")
        assert len(eng._recommendations) == 2


# ---------------------------------------------------------------------------
# analyze_scaling_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeScalingDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_scaling(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
            efficiency_score=60.0,
        )
        eng.record_scaling(
            scaling_id="SCL-002",
            scaling_action=ScalingAction.SCALE_UP,
            efficiency_score=80.0,
        )
        result = eng.analyze_scaling_distribution()
        assert "scale_up" in result
        assert result["scale_up"]["count"] == 2
        assert result["scale_up"]["avg_efficiency_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_scaling_distribution() == {}


# ---------------------------------------------------------------------------
# identify_inefficient_scaling
# ---------------------------------------------------------------------------


class TestIdentifyInefficientScaling:
    def test_detects_over_and_under(self):
        eng = _engine()
        eng.record_scaling(
            scaling_id="SCL-001",
            provisioning_status=ProvisioningStatus.OVER_PROVISIONED,
        )
        eng.record_scaling(
            scaling_id="SCL-002",
            provisioning_status=ProvisioningStatus.UNDER_PROVISIONED,
        )
        eng.record_scaling(
            scaling_id="SCL-003",
            provisioning_status=ProvisioningStatus.RIGHT_SIZED,
        )
        results = eng.identify_inefficient_scaling()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inefficient_scaling() == []


# ---------------------------------------------------------------------------
# rank_by_efficiency
# ---------------------------------------------------------------------------


class TestRankByEfficiency:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_scaling(scaling_id="SCL-001", service="api", efficiency_score=90.0)
        eng.record_scaling(scaling_id="SCL-002", service="db", efficiency_score=30.0)
        results = eng.rank_by_efficiency()
        assert len(results) == 2
        assert results[0]["service"] == "db"
        assert results[0]["avg_efficiency_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_efficiency() == []


# ---------------------------------------------------------------------------
# detect_scaling_trends
# ---------------------------------------------------------------------------


class TestDetectScalingTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_recommendation(scaling_id="SCL-001", recommendation_score=50.0)
        result = eng.detect_scaling_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_recommendation(scaling_id="SCL-001", recommendation_score=30.0)
        eng.add_recommendation(scaling_id="SCL-002", recommendation_score=30.0)
        eng.add_recommendation(scaling_id="SCL-003", recommendation_score=80.0)
        eng.add_recommendation(scaling_id="SCL-004", recommendation_score=80.0)
        result = eng.detect_scaling_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_scaling_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_scaling(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
            provisioning_status=ProvisioningStatus.UNDER_PROVISIONED,
            efficiency_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CapacityScalingReport)
        assert report.total_records == 1
        assert report.inefficient_count == 1
        assert len(report.top_inefficient) == 1
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
        eng.record_scaling(scaling_id="SCL-001")
        eng.add_recommendation(scaling_id="SCL-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._recommendations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["action_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_scaling(
            scaling_id="SCL-001",
            scaling_action=ScalingAction.SCALE_UP,
            team="sre",
            service="api",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "scale_up" in stats["action_distribution"]

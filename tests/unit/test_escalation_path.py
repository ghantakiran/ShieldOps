"""Tests for shieldops.incidents.escalation_path — EscalationPathAnalyzer."""

from __future__ import annotations

from shieldops.incidents.escalation_path import (
    BottleneckType,
    EscalationPathAnalyzer,
    EscalationPathRecord,
    EscalationPathReport,
    EscalationStage,
    PathEfficiency,
    PathMetric,
)


def _engine(**kw) -> EscalationPathAnalyzer:
    return EscalationPathAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_l1_triage(self):
        assert EscalationStage.L1_TRIAGE == "l1_triage"

    def test_stage_l2_investigation(self):
        assert EscalationStage.L2_INVESTIGATION == "l2_investigation"

    def test_stage_l3_specialist(self):
        assert EscalationStage.L3_SPECIALIST == "l3_specialist"

    def test_stage_l4_engineering(self):
        assert EscalationStage.L4_ENGINEERING == "l4_engineering"

    def test_stage_l5_management(self):
        assert EscalationStage.L5_MANAGEMENT == "l5_management"

    def test_efficiency_optimal(self):
        assert PathEfficiency.OPTIMAL == "optimal"

    def test_efficiency_efficient(self):
        assert PathEfficiency.EFFICIENT == "efficient"

    def test_efficiency_adequate(self):
        assert PathEfficiency.ADEQUATE == "adequate"

    def test_efficiency_inefficient(self):
        assert PathEfficiency.INEFFICIENT == "inefficient"

    def test_efficiency_broken(self):
        assert PathEfficiency.BROKEN == "broken"

    def test_bottleneck_skill_gap(self):
        assert BottleneckType.SKILL_GAP == "skill_gap"

    def test_bottleneck_availability(self):
        assert BottleneckType.AVAILABILITY == "availability"

    def test_bottleneck_process(self):
        assert BottleneckType.PROCESS == "process"

    def test_bottleneck_tooling(self):
        assert BottleneckType.TOOLING == "tooling"

    def test_bottleneck_communication(self):
        assert BottleneckType.COMMUNICATION == "communication"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_escalation_path_record_defaults(self):
        r = EscalationPathRecord()
        assert r.id
        assert r.path_id == ""
        assert r.escalation_stage == EscalationStage.L1_TRIAGE
        assert r.path_efficiency == PathEfficiency.ADEQUATE
        assert r.bottleneck_type == BottleneckType.PROCESS
        assert r.resolution_time_minutes == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_path_metric_defaults(self):
        m = PathMetric()
        assert m.id
        assert m.path_id == ""
        assert m.escalation_stage == EscalationStage.L1_TRIAGE
        assert m.metric_value == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_escalation_path_report_defaults(self):
        r = EscalationPathReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.inefficient_paths == 0
        assert r.avg_resolution_time == 0.0
        assert r.by_stage == {}
        assert r.by_efficiency == {}
        assert r.by_bottleneck == {}
        assert r.top_bottlenecks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_path
# ---------------------------------------------------------------------------


class TestRecordPath:
    def test_basic(self):
        eng = _engine()
        r = eng.record_path(
            path_id="PATH-001",
            escalation_stage=EscalationStage.L2_INVESTIGATION,
            path_efficiency=PathEfficiency.OPTIMAL,
            bottleneck_type=BottleneckType.SKILL_GAP,
            resolution_time_minutes=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.path_id == "PATH-001"
        assert r.escalation_stage == EscalationStage.L2_INVESTIGATION
        assert r.path_efficiency == PathEfficiency.OPTIMAL
        assert r.bottleneck_type == BottleneckType.SKILL_GAP
        assert r.resolution_time_minutes == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_path(path_id=f"PATH-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_path
# ---------------------------------------------------------------------------


class TestGetPath:
    def test_found(self):
        eng = _engine()
        r = eng.record_path(
            path_id="PATH-001",
            path_efficiency=PathEfficiency.BROKEN,
        )
        result = eng.get_path(r.id)
        assert result is not None
        assert result.path_efficiency == PathEfficiency.BROKEN

    def test_not_found(self):
        eng = _engine()
        assert eng.get_path("nonexistent") is None


# ---------------------------------------------------------------------------
# list_paths
# ---------------------------------------------------------------------------


class TestListPaths:
    def test_list_all(self):
        eng = _engine()
        eng.record_path(path_id="PATH-001")
        eng.record_path(path_id="PATH-002")
        assert len(eng.list_paths()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            escalation_stage=EscalationStage.L1_TRIAGE,
        )
        eng.record_path(
            path_id="PATH-002",
            escalation_stage=EscalationStage.L3_SPECIALIST,
        )
        results = eng.list_paths(
            stage=EscalationStage.L1_TRIAGE,
        )
        assert len(results) == 1

    def test_filter_by_efficiency(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            path_efficiency=PathEfficiency.OPTIMAL,
        )
        eng.record_path(
            path_id="PATH-002",
            path_efficiency=PathEfficiency.BROKEN,
        )
        results = eng.list_paths(
            efficiency=PathEfficiency.OPTIMAL,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_path(path_id="PATH-001", service="api-gateway")
        eng.record_path(path_id="PATH-002", service="auth-svc")
        results = eng.list_paths(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_path(path_id="PATH-001", team="sre")
        eng.record_path(path_id="PATH-002", team="platform")
        results = eng.list_paths(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_path(path_id=f"PATH-{i}")
        assert len(eng.list_paths(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            path_id="PATH-001",
            escalation_stage=EscalationStage.L2_INVESTIGATION,
            metric_value=85.0,
            threshold=90.0,
            breached=True,
            description="Resolution time exceeded",
        )
        assert m.path_id == "PATH-001"
        assert m.escalation_stage == EscalationStage.L2_INVESTIGATION
        assert m.metric_value == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Resolution time exceeded"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(path_id=f"PATH-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_path_efficiency
# ---------------------------------------------------------------------------


class TestAnalyzePathEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            escalation_stage=EscalationStage.L1_TRIAGE,
            resolution_time_minutes=30.0,
        )
        eng.record_path(
            path_id="PATH-002",
            escalation_stage=EscalationStage.L1_TRIAGE,
            resolution_time_minutes=60.0,
        )
        result = eng.analyze_path_efficiency()
        assert "l1_triage" in result
        assert result["l1_triage"]["count"] == 2
        assert result["l1_triage"]["avg_resolution_time"] == 45.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_path_efficiency() == {}


# ---------------------------------------------------------------------------
# identify_inefficient_paths
# ---------------------------------------------------------------------------


class TestIdentifyInefficientPaths:
    def test_detects_inefficient(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            path_efficiency=PathEfficiency.INEFFICIENT,
        )
        eng.record_path(
            path_id="PATH-002",
            path_efficiency=PathEfficiency.OPTIMAL,
        )
        results = eng.identify_inefficient_paths()
        assert len(results) == 1
        assert results[0]["path_id"] == "PATH-001"

    def test_detects_broken(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            path_efficiency=PathEfficiency.BROKEN,
        )
        results = eng.identify_inefficient_paths()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inefficient_paths() == []


# ---------------------------------------------------------------------------
# rank_by_resolution_time
# ---------------------------------------------------------------------------


class TestRankByResolutionTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            service="api-gateway",
            resolution_time_minutes=120.0,
        )
        eng.record_path(
            path_id="PATH-002",
            service="auth-svc",
            resolution_time_minutes=30.0,
        )
        results = eng.rank_by_resolution_time()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_resolution_time"] == 120.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_resolution_time() == []


# ---------------------------------------------------------------------------
# detect_efficiency_trends
# ---------------------------------------------------------------------------


class TestDetectEfficiencyTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_metric(path_id="PATH-1", metric_value=val)
        result = eng.detect_efficiency_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_metric(path_id="PATH-1", metric_value=val)
        result = eng.detect_efficiency_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_efficiency_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            escalation_stage=EscalationStage.L3_SPECIALIST,
            path_efficiency=PathEfficiency.INEFFICIENT,
            bottleneck_type=BottleneckType.SKILL_GAP,
            resolution_time_minutes=180.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, EscalationPathReport)
        assert report.total_records == 1
        assert report.inefficient_paths == 1
        assert len(report.top_bottlenecks) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_path(path_id="PATH-001")
        eng.add_metric(path_id="PATH-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_path(
            path_id="PATH-001",
            escalation_stage=EscalationStage.L1_TRIAGE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "l1_triage" in stats["stage_distribution"]

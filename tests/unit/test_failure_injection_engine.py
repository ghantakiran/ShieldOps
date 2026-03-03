"""Tests for shieldops.operations.failure_injection_engine."""

from __future__ import annotations

from shieldops.operations.failure_injection_engine import (
    FailureInjection,
    FailureInjectionEngine,
    FailureType,
    InjectionAnalysis,
    InjectionReport,
    InjectionScope,
    SafetyLevel,
)


def _engine(**kw) -> FailureInjectionEngine:
    return FailureInjectionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_failure_type_process_kill(self):
        assert FailureType.PROCESS_KILL == "process_kill"

    def test_failure_type_network_drop(self):
        assert FailureType.NETWORK_DROP == "network_drop"

    def test_failure_type_disk_full(self):
        assert FailureType.DISK_FULL == "disk_full"

    def test_failure_type_cpu_stress(self):
        assert FailureType.CPU_STRESS == "cpu_stress"

    def test_failure_type_memory_pressure(self):
        assert FailureType.MEMORY_PRESSURE == "memory_pressure"

    def test_scope_pod(self):
        assert InjectionScope.POD == "pod"

    def test_scope_node(self):
        assert InjectionScope.NODE == "node"

    def test_scope_namespace(self):
        assert InjectionScope.NAMESPACE == "namespace"

    def test_scope_cluster(self):
        assert InjectionScope.CLUSTER == "cluster"

    def test_scope_region(self):
        assert InjectionScope.REGION == "region"

    def test_safety_safe(self):
        assert SafetyLevel.SAFE == "safe"

    def test_safety_moderate(self):
        assert SafetyLevel.MODERATE == "moderate"

    def test_safety_aggressive(self):
        assert SafetyLevel.AGGRESSIVE == "aggressive"

    def test_safety_destructive(self):
        assert SafetyLevel.DESTRUCTIVE == "destructive"

    def test_safety_custom(self):
        assert SafetyLevel.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_failure_injection_defaults(self):
        r = FailureInjection()
        assert r.id
        assert r.failure_type == FailureType.PROCESS_KILL
        assert r.injection_scope == InjectionScope.POD
        assert r.safety_level == SafetyLevel.SAFE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_injection_analysis_defaults(self):
        a = InjectionAnalysis()
        assert a.id
        assert a.failure_type == FailureType.PROCESS_KILL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_injection_report_defaults(self):
        r = InjectionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_failure_type == {}
        assert r.by_scope == {}
        assert r.by_safety == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=500)
        assert eng._max_records == 500

    def test_custom_threshold(self):
        eng = _engine(threshold=70.0)
        assert eng._threshold == 70.0


# ---------------------------------------------------------------------------
# record_injection / get_injection
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_injection(
            service="k8s-svc",
            failure_type=FailureType.NETWORK_DROP,
            injection_scope=InjectionScope.NODE,
            safety_level=SafetyLevel.MODERATE,
            score=75.0,
            team="sre",
        )
        assert r.service == "k8s-svc"
        assert r.failure_type == FailureType.NETWORK_DROP
        assert r.injection_scope == InjectionScope.NODE
        assert r.safety_level == SafetyLevel.MODERATE
        assert r.score == 75.0
        assert r.team == "sre"

    def test_record_stored(self):
        eng = _engine()
        eng.record_injection(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_injection(service="svc-a", score=60.0)
        result = eng.get_injection(r.id)
        assert result is not None
        assert result.score == 60.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_injection("nonexistent") is None


# ---------------------------------------------------------------------------
# list_injections
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_injection(service="svc-a")
        eng.record_injection(service="svc-b")
        assert len(eng.list_injections()) == 2

    def test_filter_by_failure_type(self):
        eng = _engine()
        eng.record_injection(service="svc-a", failure_type=FailureType.PROCESS_KILL)
        eng.record_injection(service="svc-b", failure_type=FailureType.DISK_FULL)
        results = eng.list_injections(failure_type=FailureType.PROCESS_KILL)
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_injection(service="svc-a", injection_scope=InjectionScope.POD)
        eng.record_injection(service="svc-b", injection_scope=InjectionScope.CLUSTER)
        results = eng.list_injections(injection_scope=InjectionScope.POD)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_injection(service="svc-a", team="sre")
        eng.record_injection(service="svc-b", team="security")
        assert len(eng.list_injections(team="sre")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_injection(service=f"svc-{i}")
        assert len(eng.list_injections(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            failure_type=FailureType.CPU_STRESS,
            analysis_score=70.0,
            threshold=60.0,
            breached=True,
            description="cpu stress detected",
        )
        assert a.failure_type == FailureType.CPU_STRESS
        assert a.analysis_score == 70.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_injection(service="s1", failure_type=FailureType.PROCESS_KILL, score=90.0)
        eng.record_injection(service="s2", failure_type=FailureType.PROCESS_KILL, score=70.0)
        result = eng.analyze_distribution()
        assert "process_kill" in result
        assert result["process_kill"]["count"] == 2
        assert result["process_kill"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_safety_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_injection(service="svc-a", score=60.0)
        eng.record_injection(service="svc-b", score=90.0)
        results = eng.identify_safety_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_injection(service="svc-a", score=50.0)
        eng.record_injection(service="svc-b", score=30.0)
        results = eng.identify_safety_gaps()
        assert results[0]["score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_injection(service="svc-a", score=90.0)
        eng.record_injection(service="svc-b", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_injection(
            service="svc-a",
            failure_type=FailureType.DISK_FULL,
            injection_scope=InjectionScope.NODE,
            safety_level=SafetyLevel.MODERATE,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, InjectionReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_injection(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_injection(
            service="svc-a",
            failure_type=FailureType.PROCESS_KILL,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "process_kill" in stats["type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_injection(service=f"svc-{i}")
        assert len(eng._records) == 3

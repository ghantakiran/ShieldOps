"""Tests for shieldops.topology.reliability_antipattern — ReliabilityAntiPatternDetector."""

from __future__ import annotations

from shieldops.topology.reliability_antipattern import (
    AntiPatternRecord,
    AntiPatternType,
    DetectionMethod,
    ReliabilityAntiPatternDetector,
    ReliabilityAntiPatternReport,
    RemediationPlan,
    RemediationUrgency,
)


def _engine(**kw) -> ReliabilityAntiPatternDetector:
    return ReliabilityAntiPatternDetector(**kw)


class TestEnums:
    def test_type_spof(self):
        assert AntiPatternType.SINGLE_POINT_OF_FAILURE == "single_point_of_failure"

    def test_type_cascading(self):
        assert AntiPatternType.CASCADING_DEPENDENCY == "cascading_dependency"

    def test_type_missing_retry(self):
        assert AntiPatternType.MISSING_RETRY == "missing_retry"

    def test_type_no_circuit_breaker(self):
        assert AntiPatternType.NO_CIRCUIT_BREAKER == "no_circuit_breaker"

    def test_type_sync_chain(self):
        assert AntiPatternType.SYNCHRONOUS_CHAIN == "synchronous_chain"

    def test_method_static(self):
        assert DetectionMethod.STATIC_ANALYSIS == "static_analysis"

    def test_method_runtime(self):
        assert DetectionMethod.RUNTIME_OBSERVATION == "runtime_observation"

    def test_method_dependency(self):
        assert DetectionMethod.DEPENDENCY_GRAPH == "dependency_graph"

    def test_method_failure(self):
        assert DetectionMethod.FAILURE_CORRELATION == "failure_correlation"

    def test_method_manual(self):
        assert DetectionMethod.MANUAL_REVIEW == "manual_review"

    def test_urgency_immediate(self):
        assert RemediationUrgency.IMMEDIATE == "immediate"

    def test_urgency_short_term(self):
        assert RemediationUrgency.SHORT_TERM == "short_term"

    def test_urgency_medium_term(self):
        assert RemediationUrgency.MEDIUM_TERM == "medium_term"

    def test_urgency_long_term(self):
        assert RemediationUrgency.LONG_TERM == "long_term"

    def test_urgency_accepted_risk(self):
        assert RemediationUrgency.ACCEPTED_RISK == "accepted_risk"


class TestModels:
    def test_antipattern_record_defaults(self):
        r = AntiPatternRecord()
        assert r.id
        assert r.service_name == ""
        assert r.pattern_type == AntiPatternType.SINGLE_POINT_OF_FAILURE
        assert r.detection_method == DetectionMethod.STATIC_ANALYSIS
        assert r.urgency == RemediationUrgency.MEDIUM_TERM
        assert r.impact_score == 0.0
        assert r.affected_services_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_remediation_plan_defaults(self):
        r = RemediationPlan()
        assert r.id
        assert r.pattern_id == ""
        assert r.plan_name == ""
        assert r.urgency == RemediationUrgency.MEDIUM_TERM
        assert r.estimated_effort_days == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ReliabilityAntiPatternReport()
        assert r.total_patterns == 0
        assert r.total_plans == 0
        assert r.avg_impact_score == 0.0
        assert r.by_pattern_type == {}
        assert r.by_urgency == {}
        assert r.immediate_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordPattern:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pattern(
            "svc-a",
            pattern_type=AntiPatternType.SINGLE_POINT_OF_FAILURE,
            impact_score=85.0,
        )
        assert r.service_name == "svc-a"
        assert r.impact_score == 85.0

    def test_with_urgency(self):
        eng = _engine()
        r = eng.record_pattern("svc-b", urgency=RemediationUrgency.IMMEDIATE)
        assert r.urgency == RemediationUrgency.IMMEDIATE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pattern(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetPattern:
    def test_found(self):
        eng = _engine()
        r = eng.record_pattern("svc-a")
        assert eng.get_pattern(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pattern("nonexistent") is None


class TestListPatterns:
    def test_list_all(self):
        eng = _engine()
        eng.record_pattern("svc-a")
        eng.record_pattern("svc-b")
        assert len(eng.list_patterns()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_pattern("svc-a")
        eng.record_pattern("svc-b")
        results = eng.list_patterns(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_pattern("svc-a", pattern_type=AntiPatternType.MISSING_RETRY)
        eng.record_pattern(
            "svc-b",
            pattern_type=AntiPatternType.CASCADING_DEPENDENCY,
        )
        results = eng.list_patterns(pattern_type=AntiPatternType.MISSING_RETRY)
        assert len(results) == 1


class TestAddRemediationPlan:
    def test_basic(self):
        eng = _engine()
        p = eng.add_remediation_plan(
            "pat-1",
            "add-retry-logic",
            estimated_effort_days=5.0,
        )
        assert p.plan_name == "add-retry-logic"
        assert p.estimated_effort_days == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_remediation_plan(f"pat-{i}", f"plan-{i}")
        assert len(eng._plans) == 2


class TestAnalyzeServiceAntipatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_pattern("svc-a", impact_score=80.0)
        result = eng.analyze_service_antipatterns("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_patterns"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_antipatterns("ghost")
        assert result["status"] == "no_data"


class TestIdentifyImmediateRisks:
    def test_with_immediate(self):
        eng = _engine()
        eng.record_pattern("svc-a", urgency=RemediationUrgency.IMMEDIATE)
        eng.record_pattern("svc-b", urgency=RemediationUrgency.LONG_TERM)
        results = eng.identify_immediate_risks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_immediate_risks() == []


class TestRankByImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_pattern("svc-a", impact_score=30.0)
        eng.record_pattern("svc-b", impact_score=90.0)
        results = eng.rank_by_impact()
        assert results[0]["impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


class TestDetectSystemicIssues:
    def test_with_systemic(self):
        eng = _engine()
        eng.record_pattern("svc-a", pattern_type=AntiPatternType.MISSING_RETRY)
        eng.record_pattern("svc-b", pattern_type=AntiPatternType.MISSING_RETRY)
        eng.record_pattern(
            "svc-c",
            pattern_type=AntiPatternType.CASCADING_DEPENDENCY,
        )
        results = eng.detect_systemic_issues()
        assert len(results) == 1
        assert results[0]["service_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.detect_systemic_issues() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_pattern("svc-a", urgency=RemediationUrgency.IMMEDIATE)
        eng.add_remediation_plan("pat-1", "plan-1")
        report = eng.generate_report()
        assert report.total_patterns == 1
        assert report.total_plans == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_patterns == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_pattern("svc-a")
        eng.add_remediation_plan("pat-1", "plan-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._plans) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_patterns"] == 0
        assert stats["total_plans"] == 0
        assert stats["pattern_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_pattern("svc-a", pattern_type=AntiPatternType.MISSING_RETRY)
        eng.record_pattern(
            "svc-b",
            pattern_type=AntiPatternType.CASCADING_DEPENDENCY,
        )
        eng.add_remediation_plan("pat-1", "plan-1")
        stats = eng.get_stats()
        assert stats["total_patterns"] == 2
        assert stats["total_plans"] == 1
        assert stats["unique_services"] == 2

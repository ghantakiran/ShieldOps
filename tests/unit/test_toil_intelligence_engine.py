"""Tests for shieldops.operations.toil_intelligence_engine — ToilIntelligenceEngine."""

from __future__ import annotations

from shieldops.operations.toil_intelligence_engine import (
    ToilCategory,
    ToilIntelAnalysis,
    ToilIntelligenceEngine,
    ToilIntelligenceReport,
    ToilIntelRecord,
    ToilPriority,
    ToilSource,
)


def _engine(**kw) -> ToilIntelligenceEngine:
    return ToilIntelligenceEngine(**kw)


class TestEnums:
    def test_toil_category_manual_process(self):
        assert ToilCategory.MANUAL_PROCESS == "manual_process"

    def test_toil_category_repetitive_task(self):
        assert ToilCategory.REPETITIVE_TASK == "repetitive_task"

    def test_toil_category_interrupt_driven(self):
        assert ToilCategory.INTERRUPT_DRIVEN == "interrupt_driven"

    def test_toil_category_scaling(self):
        assert ToilCategory.SCALING == "scaling"

    def test_toil_category_deployment(self):
        assert ToilCategory.DEPLOYMENT == "deployment"

    def test_toil_source_task_tracking(self):
        assert ToilSource.TASK_TRACKING == "task_tracking"

    def test_toil_source_runbook_logs(self):
        assert ToilSource.RUNBOOK_LOGS == "runbook_logs"

    def test_toil_source_oncall_data(self):
        assert ToilSource.ONCALL_DATA == "oncall_data"

    def test_toil_source_survey(self):
        assert ToilSource.SURVEY == "survey"

    def test_toil_source_automated_detection(self):
        assert ToilSource.AUTOMATED_DETECTION == "automated_detection"

    def test_toil_priority_critical(self):
        assert ToilPriority.CRITICAL == "critical"

    def test_toil_priority_high(self):
        assert ToilPriority.HIGH == "high"

    def test_toil_priority_medium(self):
        assert ToilPriority.MEDIUM == "medium"

    def test_toil_priority_low(self):
        assert ToilPriority.LOW == "low"

    def test_toil_priority_acceptable(self):
        assert ToilPriority.ACCEPTABLE == "acceptable"


class TestModels:
    def test_record_defaults(self):
        r = ToilIntelRecord()
        assert r.id
        assert r.name == ""
        assert r.toil_category == ToilCategory.MANUAL_PROCESS
        assert r.toil_source == ToilSource.TASK_TRACKING
        assert r.toil_priority == ToilPriority.ACCEPTABLE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ToilIntelAnalysis()
        assert a.id
        assert a.name == ""
        assert a.toil_category == ToilCategory.MANUAL_PROCESS
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ToilIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_toil_category == {}
        assert r.by_toil_source == {}
        assert r.by_toil_priority == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            toil_category=ToilCategory.MANUAL_PROCESS,
            toil_source=ToilSource.RUNBOOK_LOGS,
            toil_priority=ToilPriority.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.toil_category == ToilCategory.MANUAL_PROCESS
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_toil_category(self):
        eng = _engine()
        eng.record_entry(name="a", toil_category=ToilCategory.MANUAL_PROCESS)
        eng.record_entry(name="b", toil_category=ToilCategory.REPETITIVE_TASK)
        assert len(eng.list_records(toil_category=ToilCategory.MANUAL_PROCESS)) == 1

    def test_filter_by_toil_source(self):
        eng = _engine()
        eng.record_entry(name="a", toil_source=ToilSource.TASK_TRACKING)
        eng.record_entry(name="b", toil_source=ToilSource.RUNBOOK_LOGS)
        assert len(eng.list_records(toil_source=ToilSource.TASK_TRACKING)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", toil_category=ToilCategory.REPETITIVE_TASK, score=90.0)
        eng.record_entry(name="b", toil_category=ToilCategory.REPETITIVE_TASK, score=70.0)
        result = eng.analyze_distribution()
        assert "repetitive_task" in result
        assert result["repetitive_task"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

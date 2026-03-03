"""Tests for shieldops.operations.autonomous_healing_orchestrator

AutonomousHealingOrchestrator.
"""

from __future__ import annotations

from shieldops.operations.autonomous_healing_orchestrator import (
    AutonomousHealingOrchestrator,
    AutonomousHealingReport,
    HealingAction,
    HealingAnalysis,
    HealingOutcome,
    HealingRecord,
    HealingTrigger,
)


def _engine(**kw) -> AutonomousHealingOrchestrator:
    return AutonomousHealingOrchestrator(**kw)


class TestEnums:
    def test_healing_action_restart(self):
        assert HealingAction.RESTART == "restart"

    def test_healing_action_failover(self):
        assert HealingAction.FAILOVER == "failover"

    def test_healing_action_repair(self):
        assert HealingAction.REPAIR == "repair"

    def test_healing_action_reconfigure(self):
        assert HealingAction.RECONFIGURE == "reconfigure"

    def test_healing_action_replace(self):
        assert HealingAction.REPLACE == "replace"

    def test_healing_trigger_health_check(self):
        assert HealingTrigger.HEALTH_CHECK == "health_check"

    def test_healing_trigger_anomaly(self):
        assert HealingTrigger.ANOMALY == "anomaly"

    def test_healing_trigger_threshold(self):
        assert HealingTrigger.THRESHOLD == "threshold"

    def test_healing_trigger_dependency_failure(self):
        assert HealingTrigger.DEPENDENCY_FAILURE == "dependency_failure"

    def test_healing_trigger_manual(self):
        assert HealingTrigger.MANUAL == "manual"

    def test_healing_outcome_healed(self):
        assert HealingOutcome.HEALED == "healed"

    def test_healing_outcome_partial(self):
        assert HealingOutcome.PARTIAL == "partial"

    def test_healing_outcome_failed(self):
        assert HealingOutcome.FAILED == "failed"

    def test_healing_outcome_escalated(self):
        assert HealingOutcome.ESCALATED == "escalated"

    def test_healing_outcome_deferred(self):
        assert HealingOutcome.DEFERRED == "deferred"


class TestModels:
    def test_record_defaults(self):
        r = HealingRecord()
        assert r.id
        assert r.name == ""
        assert r.healing_action == HealingAction.RESTART
        assert r.healing_trigger == HealingTrigger.HEALTH_CHECK
        assert r.healing_outcome == HealingOutcome.DEFERRED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = HealingAnalysis()
        assert a.id
        assert a.name == ""
        assert a.healing_action == HealingAction.RESTART
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutonomousHealingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_healing_action == {}
        assert r.by_healing_trigger == {}
        assert r.by_healing_outcome == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            healing_action=HealingAction.RESTART,
            healing_trigger=HealingTrigger.ANOMALY,
            healing_outcome=HealingOutcome.HEALED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.healing_action == HealingAction.RESTART
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

    def test_filter_by_healing_action(self):
        eng = _engine()
        eng.record_entry(name="a", healing_action=HealingAction.RESTART)
        eng.record_entry(name="b", healing_action=HealingAction.FAILOVER)
        assert len(eng.list_records(healing_action=HealingAction.RESTART)) == 1

    def test_filter_by_healing_trigger(self):
        eng = _engine()
        eng.record_entry(name="a", healing_trigger=HealingTrigger.HEALTH_CHECK)
        eng.record_entry(name="b", healing_trigger=HealingTrigger.ANOMALY)
        assert len(eng.list_records(healing_trigger=HealingTrigger.HEALTH_CHECK)) == 1

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
        eng.record_entry(name="a", healing_action=HealingAction.FAILOVER, score=90.0)
        eng.record_entry(name="b", healing_action=HealingAction.FAILOVER, score=70.0)
        result = eng.analyze_distribution()
        assert "failover" in result
        assert result["failover"]["count"] == 2

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

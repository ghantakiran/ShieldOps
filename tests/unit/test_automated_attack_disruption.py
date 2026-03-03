"""Tests for shieldops.security.automated_attack_disruption — AutomatedAttackDisruption."""

from __future__ import annotations

from shieldops.security.automated_attack_disruption import (
    AttackStage,
    AutomatedAttackDisruption,
    AutomatedAttackDisruptionAnalysis,
    AutomatedAttackDisruptionRecord,
    AutomatedAttackDisruptionReport,
    DisruptionMethod,
    DisruptionResult,
)


def _engine(**kw) -> AutomatedAttackDisruption:
    return AutomatedAttackDisruption(**kw)


class TestEnums:
    def test_disruption_method_first(self):
        assert DisruptionMethod.BLOCK == "block"

    def test_disruption_method_second(self):
        assert DisruptionMethod.DECEIVE == "deceive"

    def test_disruption_method_third(self):
        assert DisruptionMethod.DELAY == "delay"

    def test_disruption_method_fourth(self):
        assert DisruptionMethod.DEGRADE == "degrade"

    def test_disruption_method_fifth(self):
        assert DisruptionMethod.DISCONNECT == "disconnect"

    def test_attack_stage_first(self):
        assert AttackStage.INITIAL_ACCESS == "initial_access"

    def test_attack_stage_second(self):
        assert AttackStage.EXECUTION == "execution"

    def test_attack_stage_third(self):
        assert AttackStage.PERSISTENCE == "persistence"

    def test_attack_stage_fourth(self):
        assert AttackStage.LATERAL_MOVEMENT == "lateral_movement"

    def test_attack_stage_fifth(self):
        assert AttackStage.EXFILTRATION == "exfiltration"

    def test_disruption_result_first(self):
        assert DisruptionResult.DISRUPTED == "disrupted"

    def test_disruption_result_second(self):
        assert DisruptionResult.PARTIALLY_DISRUPTED == "partially_disrupted"

    def test_disruption_result_third(self):
        assert DisruptionResult.EVADED == "evaded"

    def test_disruption_result_fourth(self):
        assert DisruptionResult.FAILED == "failed"

    def test_disruption_result_fifth(self):
        assert DisruptionResult.PENDING == "pending"


class TestModels:
    def test_record_defaults(self):
        r = AutomatedAttackDisruptionRecord()
        assert r.id
        assert r.name == ""
        assert r.disruption_method == DisruptionMethod.BLOCK
        assert r.attack_stage == AttackStage.INITIAL_ACCESS
        assert r.disruption_result == DisruptionResult.DISRUPTED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AutomatedAttackDisruptionAnalysis()
        assert a.id
        assert a.name == ""
        assert a.disruption_method == DisruptionMethod.BLOCK
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutomatedAttackDisruptionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_disruption_method == {}
        assert r.by_attack_stage == {}
        assert r.by_disruption_result == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            disruption_method=DisruptionMethod.BLOCK,
            attack_stage=AttackStage.EXECUTION,
            disruption_result=DisruptionResult.EVADED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.disruption_method == DisruptionMethod.BLOCK
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_disruption_method(self):
        eng = _engine()
        eng.record_item(name="a", disruption_method=DisruptionMethod.DECEIVE)
        eng.record_item(name="b", disruption_method=DisruptionMethod.BLOCK)
        assert len(eng.list_records(disruption_method=DisruptionMethod.DECEIVE)) == 1

    def test_filter_by_attack_stage(self):
        eng = _engine()
        eng.record_item(name="a", attack_stage=AttackStage.INITIAL_ACCESS)
        eng.record_item(name="b", attack_stage=AttackStage.EXECUTION)
        assert len(eng.list_records(attack_stage=AttackStage.INITIAL_ACCESS)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(name="a", disruption_method=DisruptionMethod.DECEIVE, score=90.0)
        eng.record_item(name="b", disruption_method=DisruptionMethod.DECEIVE, score=70.0)
        result = eng.analyze_distribution()
        assert "deceive" in result
        assert result["deceive"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

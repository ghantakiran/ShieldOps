"""Tests for shieldops.operations.automation_safety_validator — AutomationSafetyValidator."""

from __future__ import annotations

from shieldops.operations.automation_safety_validator import (
    AutomationSafetyReport,
    AutomationSafetyValidator,
    SafetyAnalysis,
    SafetyCheck,
    SafetyRecord,
    SafetySource,
    SafetyVerdict,
)


def _engine(**kw) -> AutomationSafetyValidator:
    return AutomationSafetyValidator(**kw)


class TestEnums:
    def test_safety_check_blast_radius(self):
        assert SafetyCheck.BLAST_RADIUS == "blast_radius"

    def test_safety_check_rollback_plan(self):
        assert SafetyCheck.ROLLBACK_PLAN == "rollback_plan"

    def test_safety_check_dependency_check(self):
        assert SafetyCheck.DEPENDENCY_CHECK == "dependency_check"

    def test_safety_check_approval_gate(self):
        assert SafetyCheck.APPROVAL_GATE == "approval_gate"

    def test_safety_check_canary(self):
        assert SafetyCheck.CANARY == "canary"

    def test_safety_source_policy_engine(self):
        assert SafetySource.POLICY_ENGINE == "policy_engine"

    def test_safety_source_historical_data(self):
        assert SafetySource.HISTORICAL_DATA == "historical_data"

    def test_safety_source_simulation(self):
        assert SafetySource.SIMULATION == "simulation"

    def test_safety_source_peer_review(self):
        assert SafetySource.PEER_REVIEW == "peer_review"

    def test_safety_source_automated(self):
        assert SafetySource.AUTOMATED == "automated"

    def test_safety_verdict_safe(self):
        assert SafetyVerdict.SAFE == "safe"

    def test_safety_verdict_conditional(self):
        assert SafetyVerdict.CONDITIONAL == "conditional"

    def test_safety_verdict_risky(self):
        assert SafetyVerdict.RISKY == "risky"

    def test_safety_verdict_blocked(self):
        assert SafetyVerdict.BLOCKED == "blocked"

    def test_safety_verdict_override_required(self):
        assert SafetyVerdict.OVERRIDE_REQUIRED == "override_required"


class TestModels:
    def test_record_defaults(self):
        r = SafetyRecord()
        assert r.id
        assert r.name == ""
        assert r.safety_check == SafetyCheck.BLAST_RADIUS
        assert r.safety_source == SafetySource.POLICY_ENGINE
        assert r.safety_verdict == SafetyVerdict.OVERRIDE_REQUIRED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SafetyAnalysis()
        assert a.id
        assert a.name == ""
        assert a.safety_check == SafetyCheck.BLAST_RADIUS
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutomationSafetyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_safety_check == {}
        assert r.by_safety_source == {}
        assert r.by_safety_verdict == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            safety_check=SafetyCheck.BLAST_RADIUS,
            safety_source=SafetySource.HISTORICAL_DATA,
            safety_verdict=SafetyVerdict.SAFE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.safety_check == SafetyCheck.BLAST_RADIUS
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

    def test_filter_by_safety_check(self):
        eng = _engine()
        eng.record_entry(name="a", safety_check=SafetyCheck.BLAST_RADIUS)
        eng.record_entry(name="b", safety_check=SafetyCheck.ROLLBACK_PLAN)
        assert len(eng.list_records(safety_check=SafetyCheck.BLAST_RADIUS)) == 1

    def test_filter_by_safety_source(self):
        eng = _engine()
        eng.record_entry(name="a", safety_source=SafetySource.POLICY_ENGINE)
        eng.record_entry(name="b", safety_source=SafetySource.HISTORICAL_DATA)
        assert len(eng.list_records(safety_source=SafetySource.POLICY_ENGINE)) == 1

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
        eng.record_entry(name="a", safety_check=SafetyCheck.ROLLBACK_PLAN, score=90.0)
        eng.record_entry(name="b", safety_check=SafetyCheck.ROLLBACK_PLAN, score=70.0)
        result = eng.analyze_distribution()
        assert "rollback_plan" in result
        assert result["rollback_plan"]["count"] == 2

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

"""Tests for shieldops.operations.multi_region_failover_automator — MultiRegionFailoverAutomator."""

from __future__ import annotations

from shieldops.operations.multi_region_failover_automator import (
    FailoverAnalysis,
    FailoverRecord,
    FailoverStatus,
    FailoverTrigger,
    FailoverType,
    MultiRegionFailoverAutomator,
    MultiRegionFailoverReport,
)


def _engine(**kw) -> MultiRegionFailoverAutomator:
    return MultiRegionFailoverAutomator(**kw)


class TestEnums:
    def test_failover_type_active_passive(self):
        assert FailoverType.ACTIVE_PASSIVE == "active_passive"

    def test_failover_type_active_active(self):
        assert FailoverType.ACTIVE_ACTIVE == "active_active"

    def test_failover_type_pilot_light(self):
        assert FailoverType.PILOT_LIGHT == "pilot_light"

    def test_failover_type_warm_standby(self):
        assert FailoverType.WARM_STANDBY == "warm_standby"

    def test_failover_type_multi_site(self):
        assert FailoverType.MULTI_SITE == "multi_site"

    def test_failover_trigger_health_check(self):
        assert FailoverTrigger.HEALTH_CHECK == "health_check"

    def test_failover_trigger_region_outage(self):
        assert FailoverTrigger.REGION_OUTAGE == "region_outage"

    def test_failover_trigger_degradation(self):
        assert FailoverTrigger.DEGRADATION == "degradation"

    def test_failover_trigger_scheduled(self):
        assert FailoverTrigger.SCHEDULED == "scheduled"

    def test_failover_trigger_manual(self):
        assert FailoverTrigger.MANUAL == "manual"

    def test_failover_status_completed(self):
        assert FailoverStatus.COMPLETED == "completed"

    def test_failover_status_in_progress(self):
        assert FailoverStatus.IN_PROGRESS == "in_progress"

    def test_failover_status_failed(self):
        assert FailoverStatus.FAILED == "failed"

    def test_failover_status_partial(self):
        assert FailoverStatus.PARTIAL == "partial"

    def test_failover_status_rolled_back(self):
        assert FailoverStatus.ROLLED_BACK == "rolled_back"


class TestModels:
    def test_record_defaults(self):
        r = FailoverRecord()
        assert r.id
        assert r.name == ""
        assert r.failover_type == FailoverType.ACTIVE_PASSIVE
        assert r.failover_trigger == FailoverTrigger.HEALTH_CHECK
        assert r.failover_status == FailoverStatus.ROLLED_BACK
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = FailoverAnalysis()
        assert a.id
        assert a.name == ""
        assert a.failover_type == FailoverType.ACTIVE_PASSIVE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = MultiRegionFailoverReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_failover_type == {}
        assert r.by_failover_trigger == {}
        assert r.by_failover_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            failover_type=FailoverType.ACTIVE_PASSIVE,
            failover_trigger=FailoverTrigger.REGION_OUTAGE,
            failover_status=FailoverStatus.COMPLETED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.failover_type == FailoverType.ACTIVE_PASSIVE
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

    def test_filter_by_failover_type(self):
        eng = _engine()
        eng.record_entry(name="a", failover_type=FailoverType.ACTIVE_PASSIVE)
        eng.record_entry(name="b", failover_type=FailoverType.ACTIVE_ACTIVE)
        assert len(eng.list_records(failover_type=FailoverType.ACTIVE_PASSIVE)) == 1

    def test_filter_by_failover_trigger(self):
        eng = _engine()
        eng.record_entry(name="a", failover_trigger=FailoverTrigger.HEALTH_CHECK)
        eng.record_entry(name="b", failover_trigger=FailoverTrigger.REGION_OUTAGE)
        assert len(eng.list_records(failover_trigger=FailoverTrigger.HEALTH_CHECK)) == 1

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
        eng.record_entry(name="a", failover_type=FailoverType.ACTIVE_ACTIVE, score=90.0)
        eng.record_entry(name="b", failover_type=FailoverType.ACTIVE_ACTIVE, score=70.0)
        result = eng.analyze_distribution()
        assert "active_active" in result
        assert result["active_active"]["count"] == 2

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

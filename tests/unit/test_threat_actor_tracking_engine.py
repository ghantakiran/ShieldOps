"""Tests for shieldops.security.threat_actor_tracking_engine — ThreatActorTrackingEngine."""

from __future__ import annotations

from shieldops.security.threat_actor_tracking_engine import (
    ActorCapability,
    ActorType,
    ThreatActorTrackingEngine,
    ThreatActorTrackingEngineAnalysis,
    ThreatActorTrackingEngineRecord,
    ThreatActorTrackingEngineReport,
    TrackingStatus,
)


def _engine(**kw) -> ThreatActorTrackingEngine:
    return ThreatActorTrackingEngine(**kw)


class TestEnums:
    def test_actor_type_first(self):
        assert ActorType.APT_GROUP == "apt_group"

    def test_actor_type_second(self):
        assert ActorType.CYBERCRIME == "cybercrime"

    def test_actor_type_third(self):
        assert ActorType.HACKTIVIST == "hacktivist"

    def test_actor_type_fourth(self):
        assert ActorType.INSIDER == "insider"

    def test_actor_type_fifth(self):
        assert ActorType.UNKNOWN == "unknown"

    def test_tracking_status_first(self):
        assert TrackingStatus.ACTIVE == "active"

    def test_tracking_status_second(self):
        assert TrackingStatus.DORMANT == "dormant"

    def test_tracking_status_third(self):
        assert TrackingStatus.RETIRED == "retired"

    def test_tracking_status_fourth(self):
        assert TrackingStatus.EMERGING == "emerging"

    def test_tracking_status_fifth(self):
        assert TrackingStatus.ATTRIBUTED == "attributed"

    def test_actor_capability_first(self):
        assert ActorCapability.ADVANCED == "advanced"

    def test_actor_capability_second(self):
        assert ActorCapability.INTERMEDIATE == "intermediate"

    def test_actor_capability_third(self):
        assert ActorCapability.BASIC == "basic"

    def test_actor_capability_fourth(self):
        assert ActorCapability.OPPORTUNISTIC == "opportunistic"

    def test_actor_capability_fifth(self):
        assert ActorCapability.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = ThreatActorTrackingEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.actor_type == ActorType.APT_GROUP
        assert r.tracking_status == TrackingStatus.ACTIVE
        assert r.actor_capability == ActorCapability.ADVANCED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ThreatActorTrackingEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.actor_type == ActorType.APT_GROUP
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ThreatActorTrackingEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_actor_type == {}
        assert r.by_tracking_status == {}
        assert r.by_actor_capability == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            actor_type=ActorType.APT_GROUP,
            tracking_status=TrackingStatus.DORMANT,
            actor_capability=ActorCapability.BASIC,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.actor_type == ActorType.APT_GROUP
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

    def test_filter_by_actor_type(self):
        eng = _engine()
        eng.record_item(name="a", actor_type=ActorType.CYBERCRIME)
        eng.record_item(name="b", actor_type=ActorType.APT_GROUP)
        assert len(eng.list_records(actor_type=ActorType.CYBERCRIME)) == 1

    def test_filter_by_tracking_status(self):
        eng = _engine()
        eng.record_item(name="a", tracking_status=TrackingStatus.ACTIVE)
        eng.record_item(name="b", tracking_status=TrackingStatus.DORMANT)
        assert len(eng.list_records(tracking_status=TrackingStatus.ACTIVE)) == 1

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
        eng.record_item(name="a", actor_type=ActorType.CYBERCRIME, score=90.0)
        eng.record_item(name="b", actor_type=ActorType.CYBERCRIME, score=70.0)
        result = eng.analyze_distribution()
        assert "cybercrime" in result
        assert result["cybercrime"]["count"] == 2

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

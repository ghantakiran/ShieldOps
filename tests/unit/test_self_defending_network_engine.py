"""Tests for shieldops.security.self_defending_network_engine — SelfDefendingNetworkEngine."""

from __future__ import annotations

from shieldops.security.self_defending_network_engine import (
    DefenseAction,
    NetworkZone,
    SelfDefendingNetworkEngine,
    SelfDefendingNetworkEngineAnalysis,
    SelfDefendingNetworkEngineRecord,
    SelfDefendingNetworkEngineReport,
    ThreatVector,
)


def _engine(**kw) -> SelfDefendingNetworkEngine:
    return SelfDefendingNetworkEngine(**kw)


class TestEnums:
    def test_defense_action_first(self):
        assert DefenseAction.SEGMENT == "segment"

    def test_defense_action_second(self):
        assert DefenseAction.BLOCK_IP == "block_ip"

    def test_defense_action_third(self):
        assert DefenseAction.RATE_LIMIT == "rate_limit"

    def test_defense_action_fourth(self):
        assert DefenseAction.REDIRECT == "redirect"

    def test_defense_action_fifth(self):
        assert DefenseAction.ISOLATE == "isolate"

    def test_network_zone_first(self):
        assert NetworkZone.DMZ == "dmz"

    def test_network_zone_second(self):
        assert NetworkZone.INTERNAL == "internal"

    def test_network_zone_third(self):
        assert NetworkZone.MANAGEMENT == "management"

    def test_network_zone_fourth(self):
        assert NetworkZone.GUEST == "guest"

    def test_network_zone_fifth(self):
        assert NetworkZone.RESTRICTED == "restricted"

    def test_threat_vector_first(self):
        assert ThreatVector.EXTERNAL == "external"

    def test_threat_vector_second(self):
        assert ThreatVector.INTERNAL == "internal"

    def test_threat_vector_third(self):
        assert ThreatVector.LATERAL == "lateral"

    def test_threat_vector_fourth(self):
        assert ThreatVector.SUPPLY_CHAIN == "supply_chain"

    def test_threat_vector_fifth(self):
        assert ThreatVector.INSIDER == "insider"


class TestModels:
    def test_record_defaults(self):
        r = SelfDefendingNetworkEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.defense_action == DefenseAction.SEGMENT
        assert r.network_zone == NetworkZone.DMZ
        assert r.threat_vector == ThreatVector.EXTERNAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SelfDefendingNetworkEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.defense_action == DefenseAction.SEGMENT
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SelfDefendingNetworkEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_defense_action == {}
        assert r.by_network_zone == {}
        assert r.by_threat_vector == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            defense_action=DefenseAction.SEGMENT,
            network_zone=NetworkZone.INTERNAL,
            threat_vector=ThreatVector.LATERAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.defense_action == DefenseAction.SEGMENT
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

    def test_filter_by_defense_action(self):
        eng = _engine()
        eng.record_item(name="a", defense_action=DefenseAction.BLOCK_IP)
        eng.record_item(name="b", defense_action=DefenseAction.SEGMENT)
        assert len(eng.list_records(defense_action=DefenseAction.BLOCK_IP)) == 1

    def test_filter_by_network_zone(self):
        eng = _engine()
        eng.record_item(name="a", network_zone=NetworkZone.DMZ)
        eng.record_item(name="b", network_zone=NetworkZone.INTERNAL)
        assert len(eng.list_records(network_zone=NetworkZone.DMZ)) == 1

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
        eng.record_item(name="a", defense_action=DefenseAction.BLOCK_IP, score=90.0)
        eng.record_item(name="b", defense_action=DefenseAction.BLOCK_IP, score=70.0)
        result = eng.analyze_distribution()
        assert "block_ip" in result
        assert result["block_ip"]["count"] == 2

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

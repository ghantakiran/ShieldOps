"""Tests for shieldops.security.multi_layer_defense_scorer — MultiLayerDefenseScorer."""

from __future__ import annotations

from shieldops.security.multi_layer_defense_scorer import (
    DefenseLayer,
    GapSeverity,
    LayerStrength,
    MultiLayerDefenseScorer,
    MultiLayerDefenseScorerAnalysis,
    MultiLayerDefenseScorerRecord,
    MultiLayerDefenseScorerReport,
)


def _engine(**kw) -> MultiLayerDefenseScorer:
    return MultiLayerDefenseScorer(**kw)


class TestEnums:
    def test_defense_layer_first(self):
        assert DefenseLayer.PERIMETER == "perimeter"

    def test_defense_layer_second(self):
        assert DefenseLayer.NETWORK == "network"

    def test_defense_layer_third(self):
        assert DefenseLayer.ENDPOINT == "endpoint"

    def test_defense_layer_fourth(self):
        assert DefenseLayer.APPLICATION == "application"

    def test_defense_layer_fifth(self):
        assert DefenseLayer.DATA == "data"

    def test_layer_strength_first(self):
        assert LayerStrength.STRONG == "strong"

    def test_layer_strength_second(self):
        assert LayerStrength.ADEQUATE == "adequate"

    def test_layer_strength_third(self):
        assert LayerStrength.WEAK == "weak"

    def test_layer_strength_fourth(self):
        assert LayerStrength.MINIMAL == "minimal"

    def test_layer_strength_fifth(self):
        assert LayerStrength.ABSENT == "absent"

    def test_gap_severity_first(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_gap_severity_second(self):
        assert GapSeverity.HIGH == "high"

    def test_gap_severity_third(self):
        assert GapSeverity.MEDIUM == "medium"

    def test_gap_severity_fourth(self):
        assert GapSeverity.LOW == "low"

    def test_gap_severity_fifth(self):
        assert GapSeverity.INFORMATIONAL == "informational"


class TestModels:
    def test_record_defaults(self):
        r = MultiLayerDefenseScorerRecord()
        assert r.id
        assert r.name == ""
        assert r.defense_layer == DefenseLayer.PERIMETER
        assert r.layer_strength == LayerStrength.STRONG
        assert r.gap_severity == GapSeverity.CRITICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = MultiLayerDefenseScorerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.defense_layer == DefenseLayer.PERIMETER
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = MultiLayerDefenseScorerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_defense_layer == {}
        assert r.by_layer_strength == {}
        assert r.by_gap_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            defense_layer=DefenseLayer.PERIMETER,
            layer_strength=LayerStrength.ADEQUATE,
            gap_severity=GapSeverity.MEDIUM,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.defense_layer == DefenseLayer.PERIMETER
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

    def test_filter_by_defense_layer(self):
        eng = _engine()
        eng.record_item(name="a", defense_layer=DefenseLayer.NETWORK)
        eng.record_item(name="b", defense_layer=DefenseLayer.PERIMETER)
        assert len(eng.list_records(defense_layer=DefenseLayer.NETWORK)) == 1

    def test_filter_by_layer_strength(self):
        eng = _engine()
        eng.record_item(name="a", layer_strength=LayerStrength.STRONG)
        eng.record_item(name="b", layer_strength=LayerStrength.ADEQUATE)
        assert len(eng.list_records(layer_strength=LayerStrength.STRONG)) == 1

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
        eng.record_item(name="a", defense_layer=DefenseLayer.NETWORK, score=90.0)
        eng.record_item(name="b", defense_layer=DefenseLayer.NETWORK, score=70.0)
        result = eng.analyze_distribution()
        assert "network" in result
        assert result["network"]["count"] == 2

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

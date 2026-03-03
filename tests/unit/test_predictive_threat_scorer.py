"""Tests for shieldops.security.predictive_threat_scorer — PredictiveThreatScorer."""

from __future__ import annotations

from shieldops.security.predictive_threat_scorer import (
    PredictionHorizon,
    PredictiveThreatScorer,
    PredictiveThreatScorerAnalysis,
    PredictiveThreatScorerRecord,
    PredictiveThreatScorerReport,
    RiskLevel,
    ThreatCategory,
)


def _engine(**kw) -> PredictiveThreatScorer:
    return PredictiveThreatScorer(**kw)


class TestEnums:
    def test_threat_category_first(self):
        assert ThreatCategory.MALWARE == "malware"

    def test_threat_category_second(self):
        assert ThreatCategory.RANSOMWARE == "ransomware"

    def test_threat_category_third(self):
        assert ThreatCategory.PHISHING == "phishing"

    def test_threat_category_fourth(self):
        assert ThreatCategory.APT == "apt"

    def test_threat_category_fifth(self):
        assert ThreatCategory.SUPPLY_CHAIN == "supply_chain"

    def test_prediction_horizon_first(self):
        assert PredictionHorizon.IMMEDIATE == "immediate"

    def test_prediction_horizon_second(self):
        assert PredictionHorizon.SHORT_TERM == "short_term"

    def test_prediction_horizon_third(self):
        assert PredictionHorizon.MEDIUM_TERM == "medium_term"

    def test_prediction_horizon_fourth(self):
        assert PredictionHorizon.LONG_TERM == "long_term"

    def test_prediction_horizon_fifth(self):
        assert PredictionHorizon.STRATEGIC == "strategic"

    def test_risk_level_first(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_level_second(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_level_third(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_level_fourth(self):
        assert RiskLevel.LOW == "low"

    def test_risk_level_fifth(self):
        assert RiskLevel.NEGLIGIBLE == "negligible"


class TestModels:
    def test_record_defaults(self):
        r = PredictiveThreatScorerRecord()
        assert r.id
        assert r.name == ""
        assert r.threat_category == ThreatCategory.MALWARE
        assert r.prediction_horizon == PredictionHorizon.IMMEDIATE
        assert r.risk_level == RiskLevel.CRITICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PredictiveThreatScorerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.threat_category == ThreatCategory.MALWARE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PredictiveThreatScorerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_threat_category == {}
        assert r.by_prediction_horizon == {}
        assert r.by_risk_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            threat_category=ThreatCategory.MALWARE,
            prediction_horizon=PredictionHorizon.SHORT_TERM,
            risk_level=RiskLevel.MEDIUM,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.threat_category == ThreatCategory.MALWARE
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

    def test_filter_by_threat_category(self):
        eng = _engine()
        eng.record_item(name="a", threat_category=ThreatCategory.RANSOMWARE)
        eng.record_item(name="b", threat_category=ThreatCategory.MALWARE)
        assert len(eng.list_records(threat_category=ThreatCategory.RANSOMWARE)) == 1

    def test_filter_by_prediction_horizon(self):
        eng = _engine()
        eng.record_item(name="a", prediction_horizon=PredictionHorizon.IMMEDIATE)
        eng.record_item(name="b", prediction_horizon=PredictionHorizon.SHORT_TERM)
        assert len(eng.list_records(prediction_horizon=PredictionHorizon.IMMEDIATE)) == 1

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
        eng.record_item(name="a", threat_category=ThreatCategory.RANSOMWARE, score=90.0)
        eng.record_item(name="b", threat_category=ThreatCategory.RANSOMWARE, score=70.0)
        result = eng.analyze_distribution()
        assert "ransomware" in result
        assert result["ransomware"]["count"] == 2

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

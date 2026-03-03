"""Tests for shieldops.sla.predictive_sla_engine — PredictiveSlaEngine."""

from __future__ import annotations

from shieldops.sla.predictive_sla_engine import (
    BreachRisk,
    MitigationPriority,
    PredictiveSlaEngine,
    PredictiveSlaEngineAnalysis,
    PredictiveSlaEngineRecord,
    PredictiveSlaEngineReport,
    SlaMetric,
)


def _engine(**kw) -> PredictiveSlaEngine:
    return PredictiveSlaEngine(**kw)


class TestEnums:
    def test_sla_metric_first(self):
        assert SlaMetric.AVAILABILITY == "availability"

    def test_sla_metric_second(self):
        assert SlaMetric.LATENCY == "latency"

    def test_sla_metric_third(self):
        assert SlaMetric.THROUGHPUT == "throughput"

    def test_sla_metric_fourth(self):
        assert SlaMetric.ERROR_RATE == "error_rate"

    def test_sla_metric_fifth(self):
        assert SlaMetric.RESPONSE_TIME == "response_time"

    def test_breach_risk_first(self):
        assert BreachRisk.IMMINENT == "imminent"

    def test_breach_risk_second(self):
        assert BreachRisk.HIGH == "high"

    def test_breach_risk_third(self):
        assert BreachRisk.MODERATE == "moderate"

    def test_breach_risk_fourth(self):
        assert BreachRisk.LOW == "low"

    def test_breach_risk_fifth(self):
        assert BreachRisk.MINIMAL == "minimal"

    def test_mitigation_priority_first(self):
        assert MitigationPriority.CRITICAL == "critical"

    def test_mitigation_priority_second(self):
        assert MitigationPriority.HIGH == "high"

    def test_mitigation_priority_third(self):
        assert MitigationPriority.MEDIUM == "medium"

    def test_mitigation_priority_fourth(self):
        assert MitigationPriority.LOW == "low"

    def test_mitigation_priority_fifth(self):
        assert MitigationPriority.DEFERRED == "deferred"


class TestModels:
    def test_record_defaults(self):
        r = PredictiveSlaEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.sla_metric == SlaMetric.AVAILABILITY
        assert r.breach_risk == BreachRisk.IMMINENT
        assert r.mitigation_priority == MitigationPriority.CRITICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PredictiveSlaEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.sla_metric == SlaMetric.AVAILABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PredictiveSlaEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_sla_metric == {}
        assert r.by_breach_risk == {}
        assert r.by_mitigation_priority == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            sla_metric=SlaMetric.AVAILABILITY,
            breach_risk=BreachRisk.HIGH,
            mitigation_priority=MitigationPriority.MEDIUM,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.sla_metric == SlaMetric.AVAILABILITY
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

    def test_filter_by_sla_metric(self):
        eng = _engine()
        eng.record_item(name="a", sla_metric=SlaMetric.LATENCY)
        eng.record_item(name="b", sla_metric=SlaMetric.AVAILABILITY)
        assert len(eng.list_records(sla_metric=SlaMetric.LATENCY)) == 1

    def test_filter_by_breach_risk(self):
        eng = _engine()
        eng.record_item(name="a", breach_risk=BreachRisk.IMMINENT)
        eng.record_item(name="b", breach_risk=BreachRisk.HIGH)
        assert len(eng.list_records(breach_risk=BreachRisk.IMMINENT)) == 1

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
        eng.record_item(name="a", sla_metric=SlaMetric.LATENCY, score=90.0)
        eng.record_item(name="b", sla_metric=SlaMetric.LATENCY, score=70.0)
        result = eng.analyze_distribution()
        assert "latency" in result
        assert result["latency"]["count"] == 2

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

"""Tests for shieldops.security.incident_correlation_engine — IncidentCorrelationEngine."""

from __future__ import annotations

from shieldops.security.incident_correlation_engine import (
    CorrelationAnalysis,
    CorrelationRecord,
    CorrelationReport,
    CorrelationStrength,
    CorrelationType,
    IncidentCorrelationEngine,
    IncidentScope,
)


def _engine(**kw) -> IncidentCorrelationEngine:
    return IncidentCorrelationEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert CorrelationType.TEMPORAL == "temporal"

    def test_e1_v2(self):
        assert CorrelationType.CAUSAL == "causal"

    def test_e1_v3(self):
        assert CorrelationType.STATISTICAL == "statistical"

    def test_e1_v4(self):
        assert CorrelationType.BEHAVIORAL == "behavioral"

    def test_e1_v5(self):
        assert CorrelationType.TOPOLOGICAL == "topological"

    def test_e2_v1(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_e2_v2(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_e2_v3(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_e2_v4(self):
        assert CorrelationStrength.COINCIDENTAL == "coincidental"

    def test_e2_v5(self):
        assert CorrelationStrength.UNKNOWN == "unknown"

    def test_e3_v1(self):
        assert IncidentScope.SINGLE == "single"

    def test_e3_v2(self):
        assert IncidentScope.MULTI_HOST == "multi_host"

    def test_e3_v3(self):
        assert IncidentScope.NETWORK_WIDE == "network_wide"

    def test_e3_v4(self):
        assert IncidentScope.CROSS_ENVIRONMENT == "cross_environment"

    def test_e3_v5(self):
        assert IncidentScope.SUPPLY_CHAIN == "supply_chain"


class TestModels:
    def test_rec(self):
        r = CorrelationRecord()
        assert r.id and r.correlation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = CorrelationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = CorrelationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_correlation(
            correlation_id="t",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.MODERATE,
            incident_scope=IncidentScope.MULTI_HOST,
            correlation_score=92.0,
            service="s",
            team="t",
        )
        assert r.correlation_id == "t" and r.correlation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(correlation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation(correlation_id="t")
        assert eng.get_correlation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_correlation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_correlation(correlation_id="a")
        eng.record_correlation(correlation_id="b")
        assert len(eng.list_correlations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_correlation(correlation_id="a", correlation_type=CorrelationType.TEMPORAL)
        eng.record_correlation(correlation_id="b", correlation_type=CorrelationType.CAUSAL)
        assert len(eng.list_correlations(correlation_type=CorrelationType.TEMPORAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_correlation(correlation_id="a", correlation_strength=CorrelationStrength.STRONG)
        eng.record_correlation(
            correlation_id="b", correlation_strength=CorrelationStrength.MODERATE
        )
        assert len(eng.list_correlations(correlation_strength=CorrelationStrength.STRONG)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_correlation(correlation_id="a", team="x")
        eng.record_correlation(correlation_id="b", team="y")
        assert len(eng.list_correlations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_correlation(correlation_id=f"t-{i}")
        assert len(eng.list_correlations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            correlation_id="t",
            correlation_type=CorrelationType.CAUSAL,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(correlation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_correlation(
            correlation_id="a", correlation_type=CorrelationType.TEMPORAL, correlation_score=90.0
        )
        eng.record_correlation(
            correlation_id="b", correlation_type=CorrelationType.TEMPORAL, correlation_score=70.0
        )
        assert "temporal" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(correlation_threshold=80.0)
        eng.record_correlation(correlation_id="a", correlation_score=60.0)
        eng.record_correlation(correlation_id="b", correlation_score=90.0)
        assert len(eng.identify_correlation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(correlation_threshold=80.0)
        eng.record_correlation(correlation_id="a", correlation_score=50.0)
        eng.record_correlation(correlation_id="b", correlation_score=30.0)
        assert len(eng.identify_correlation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_correlation(correlation_id="a", service="s1", correlation_score=80.0)
        eng.record_correlation(correlation_id="b", service="s2", correlation_score=60.0)
        assert eng.rank_by_correlation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_correlation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(correlation_id="t", analysis_score=float(v))
        assert eng.detect_correlation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(correlation_id="t", analysis_score=float(v))
        assert eng.detect_correlation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_correlation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_correlation(correlation_id="t", correlation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_correlation(correlation_id="t")
        eng.add_analysis(correlation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_correlation(correlation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_correlation(correlation_id="a")
        eng.record_correlation(correlation_id="b")
        eng.add_analysis(correlation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1

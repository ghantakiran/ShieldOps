"""Tests for shieldops.security.access_context_analyzer — AccessContextAnalyzer."""

from __future__ import annotations

from shieldops.security.access_context_analyzer import (
    AccessContextAnalyzer,
    AccessContextReport,
    AnalysisScope,
    ContextAnalysis,
    ContextFactor,
    ContextRecord,
    RiskDecision,
)


def _engine(**kw) -> AccessContextAnalyzer:
    return AccessContextAnalyzer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ContextFactor.LOCATION == "location"

    def test_e1_v2(self):
        assert ContextFactor.DEVICE == "device"

    def test_e1_v3(self):
        assert ContextFactor.TIME == "time"

    def test_e1_v4(self):
        assert ContextFactor.NETWORK == "network"

    def test_e1_v5(self):
        assert ContextFactor.BEHAVIOR == "behavior"

    def test_e2_v1(self):
        assert RiskDecision.ALLOW == "allow"

    def test_e2_v2(self):
        assert RiskDecision.DENY == "deny"

    def test_e2_v3(self):
        assert RiskDecision.CHALLENGE == "challenge"

    def test_e2_v4(self):
        assert RiskDecision.STEP_UP == "step_up"

    def test_e2_v5(self):
        assert RiskDecision.MONITOR == "monitor"

    def test_e3_v1(self):
        assert AnalysisScope.USER == "user"

    def test_e3_v2(self):
        assert AnalysisScope.APPLICATION == "application"

    def test_e3_v3(self):
        assert AnalysisScope.RESOURCE == "resource"

    def test_e3_v4(self):
        assert AnalysisScope.SESSION == "session"

    def test_e3_v5(self):
        assert AnalysisScope.TRANSACTION == "transaction"


class TestModels:
    def test_rec(self):
        r = ContextRecord()
        assert r.id and r.context_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ContextAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = AccessContextReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_context(
            context_id="t",
            context_factor=ContextFactor.DEVICE,
            risk_decision=RiskDecision.DENY,
            analysis_scope=AnalysisScope.APPLICATION,
            context_score=92.0,
            service="s",
            team="t",
        )
        assert r.context_id == "t" and r.context_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_context(context_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_context(context_id="t")
        assert eng.get_context(r.id) is not None

    def test_not_found(self):
        assert _engine().get_context("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_context(context_id="a")
        eng.record_context(context_id="b")
        assert len(eng.list_contexts()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_context(context_id="a", context_factor=ContextFactor.LOCATION)
        eng.record_context(context_id="b", context_factor=ContextFactor.DEVICE)
        assert len(eng.list_contexts(context_factor=ContextFactor.LOCATION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_context(context_id="a", risk_decision=RiskDecision.ALLOW)
        eng.record_context(context_id="b", risk_decision=RiskDecision.DENY)
        assert len(eng.list_contexts(risk_decision=RiskDecision.ALLOW)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_context(context_id="a", team="x")
        eng.record_context(context_id="b", team="y")
        assert len(eng.list_contexts(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_context(context_id=f"t-{i}")
        assert len(eng.list_contexts(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            context_id="t", context_factor=ContextFactor.DEVICE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(context_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_context(
            context_id="a", context_factor=ContextFactor.LOCATION, context_score=90.0
        )
        eng.record_context(
            context_id="b", context_factor=ContextFactor.LOCATION, context_score=70.0
        )
        assert "location" in eng.analyze_context_distribution()

    def test_empty(self):
        assert _engine().analyze_context_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(context_gap_threshold=80.0)
        eng.record_context(context_id="a", context_score=60.0)
        eng.record_context(context_id="b", context_score=90.0)
        assert len(eng.identify_context_gaps()) == 1

    def test_sorted(self):
        eng = _engine(context_gap_threshold=80.0)
        eng.record_context(context_id="a", context_score=50.0)
        eng.record_context(context_id="b", context_score=30.0)
        assert len(eng.identify_context_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_context(context_id="a", service="s1", context_score=80.0)
        eng.record_context(context_id="b", service="s2", context_score=60.0)
        assert eng.rank_by_context()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_context() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(context_id="t", analysis_score=float(v))
        assert eng.detect_context_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(context_id="t", analysis_score=float(v))
        assert eng.detect_context_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_context_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_context(context_id="t", context_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_context(context_id="t")
        eng.add_analysis(context_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_context(context_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_context(context_id="a")
        eng.record_context(context_id="b")
        eng.add_analysis(context_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1

"""Tests for shieldops.security.trust_score_calculator — TrustScoreCalculator."""

from __future__ import annotations

from shieldops.security.trust_score_calculator import (
    CalculationMethod,
    ScoreCategory,
    TrustAnalysis,
    TrustFactor,
    TrustRecord,
    TrustScoreCalculator,
    TrustScoreReport,
)


def _engine(**kw) -> TrustScoreCalculator:
    return TrustScoreCalculator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert TrustFactor.IDENTITY == "identity"

    def test_e1_v2(self):
        assert TrustFactor.DEVICE == "device"

    def test_e1_v3(self):
        assert TrustFactor.NETWORK == "network"

    def test_e1_v4(self):
        assert TrustFactor.BEHAVIOR == "behavior"

    def test_e1_v5(self):
        assert TrustFactor.CONTEXT == "context"

    def test_e2_v1(self):
        assert ScoreCategory.FULL_TRUST == "full_trust"

    def test_e2_v2(self):
        assert ScoreCategory.HIGH_TRUST == "high_trust"

    def test_e2_v3(self):
        assert ScoreCategory.CONDITIONAL == "conditional"

    def test_e2_v4(self):
        assert ScoreCategory.LOW_TRUST == "low_trust"

    def test_e2_v5(self):
        assert ScoreCategory.ZERO_TRUST == "zero_trust"

    def test_e3_v1(self):
        assert CalculationMethod.WEIGHTED == "weighted"

    def test_e3_v2(self):
        assert CalculationMethod.ML_BASED == "ml_based"

    def test_e3_v3(self):
        assert CalculationMethod.RULE_BASED == "rule_based"

    def test_e3_v4(self):
        assert CalculationMethod.HYBRID == "hybrid"

    def test_e3_v5(self):
        assert CalculationMethod.ADAPTIVE == "adaptive"


class TestModels:
    def test_rec(self):
        r = TrustRecord()
        assert r.id and r.trust_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = TrustAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = TrustScoreReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_trust(
            trust_id="t",
            trust_factor=TrustFactor.DEVICE,
            score_category=ScoreCategory.HIGH_TRUST,
            calculation_method=CalculationMethod.ML_BASED,
            trust_score=92.0,
            service="s",
            team="t",
        )
        assert r.trust_id == "t" and r.trust_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_trust(trust_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_trust(trust_id="t")
        assert eng.get_trust(r.id) is not None

    def test_not_found(self):
        assert _engine().get_trust("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_trust(trust_id="a")
        eng.record_trust(trust_id="b")
        assert len(eng.list_trusts()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_trust(trust_id="a", trust_factor=TrustFactor.IDENTITY)
        eng.record_trust(trust_id="b", trust_factor=TrustFactor.DEVICE)
        assert len(eng.list_trusts(trust_factor=TrustFactor.IDENTITY)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_trust(trust_id="a", score_category=ScoreCategory.FULL_TRUST)
        eng.record_trust(trust_id="b", score_category=ScoreCategory.HIGH_TRUST)
        assert len(eng.list_trusts(score_category=ScoreCategory.FULL_TRUST)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_trust(trust_id="a", team="x")
        eng.record_trust(trust_id="b", team="y")
        assert len(eng.list_trusts(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_trust(trust_id=f"t-{i}")
        assert len(eng.list_trusts(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            trust_id="t", trust_factor=TrustFactor.DEVICE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(trust_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_trust(trust_id="a", trust_factor=TrustFactor.IDENTITY, trust_score=90.0)
        eng.record_trust(trust_id="b", trust_factor=TrustFactor.IDENTITY, trust_score=70.0)
        assert "identity" in eng.analyze_trust_distribution()

    def test_empty(self):
        assert _engine().analyze_trust_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(trust_gap_threshold=80.0)
        eng.record_trust(trust_id="a", trust_score=60.0)
        eng.record_trust(trust_id="b", trust_score=90.0)
        assert len(eng.identify_trust_gaps()) == 1

    def test_sorted(self):
        eng = _engine(trust_gap_threshold=80.0)
        eng.record_trust(trust_id="a", trust_score=50.0)
        eng.record_trust(trust_id="b", trust_score=30.0)
        assert len(eng.identify_trust_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_trust(trust_id="a", service="s1", trust_score=80.0)
        eng.record_trust(trust_id="b", service="s2", trust_score=60.0)
        assert eng.rank_by_trust()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_trust() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(trust_id="t", analysis_score=float(v))
        assert eng.detect_trust_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(trust_id="t", analysis_score=float(v))
        assert eng.detect_trust_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_trust_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_trust(trust_id="t", trust_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_trust(trust_id="t")
        eng.add_analysis(trust_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_trust(trust_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_trust(trust_id="a")
        eng.record_trust(trust_id="b")
        eng.add_analysis(trust_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1

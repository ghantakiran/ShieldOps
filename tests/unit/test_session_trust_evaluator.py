"""Tests for shieldops.security.session_trust_evaluator — SessionTrustEvaluator."""

from __future__ import annotations

from shieldops.security.session_trust_evaluator import (
    EvaluationTrigger,
    SessionAnalysis,
    SessionRecord,
    SessionRisk,
    SessionTrustEvaluator,
    SessionTrustReport,
    TrustAction,
)


def _engine(**kw) -> SessionTrustEvaluator:
    return SessionTrustEvaluator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert SessionRisk.HIJACKED == "hijacked"

    def test_e1_v2(self):
        assert SessionRisk.SUSPICIOUS == "suspicious"

    def test_e1_v3(self):
        assert SessionRisk.ELEVATED == "elevated"

    def test_e1_v4(self):
        assert SessionRisk.NORMAL == "normal"

    def test_e1_v5(self):
        assert SessionRisk.TRUSTED == "trusted"

    def test_e2_v1(self):
        assert EvaluationTrigger.LOGIN == "login"

    def test_e2_v2(self):
        assert EvaluationTrigger.ACCESS_CHANGE == "access_change"

    def test_e2_v3(self):
        assert EvaluationTrigger.LOCATION_CHANGE == "location_change"

    def test_e2_v4(self):
        assert EvaluationTrigger.TIMEOUT == "timeout"

    def test_e2_v5(self):
        assert EvaluationTrigger.ANOMALY == "anomaly"

    def test_e3_v1(self):
        assert TrustAction.CONTINUE == "continue"

    def test_e3_v2(self):
        assert TrustAction.REAUTHENTICATE == "reauthenticate"

    def test_e3_v3(self):
        assert TrustAction.RESTRICT == "restrict"

    def test_e3_v4(self):
        assert TrustAction.TERMINATE == "terminate"

    def test_e3_v5(self):
        assert TrustAction.MONITOR == "monitor"


class TestModels:
    def test_rec(self):
        r = SessionRecord()
        assert r.id and r.evaluation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = SessionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SessionTrustReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_session(
            session_eval_id="t",
            session_risk=SessionRisk.SUSPICIOUS,
            evaluation_trigger=EvaluationTrigger.ACCESS_CHANGE,
            trust_action=TrustAction.REAUTHENTICATE,
            evaluation_score=92.0,
            service="s",
            team="t",
        )
        assert r.session_eval_id == "t" and r.evaluation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_session(session_eval_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_session(session_eval_id="t")
        assert eng.get_session(r.id) is not None

    def test_not_found(self):
        assert _engine().get_session("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_session(session_eval_id="a")
        eng.record_session(session_eval_id="b")
        assert len(eng.list_sessions()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_session(session_eval_id="a", session_risk=SessionRisk.HIJACKED)
        eng.record_session(session_eval_id="b", session_risk=SessionRisk.SUSPICIOUS)
        assert len(eng.list_sessions(session_risk=SessionRisk.HIJACKED)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_session(session_eval_id="a", evaluation_trigger=EvaluationTrigger.LOGIN)
        eng.record_session(session_eval_id="b", evaluation_trigger=EvaluationTrigger.ACCESS_CHANGE)
        assert len(eng.list_sessions(evaluation_trigger=EvaluationTrigger.LOGIN)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_session(session_eval_id="a", team="x")
        eng.record_session(session_eval_id="b", team="y")
        assert len(eng.list_sessions(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_session(session_eval_id=f"t-{i}")
        assert len(eng.list_sessions(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            session_eval_id="t",
            session_risk=SessionRisk.SUSPICIOUS,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(session_eval_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_session(
            session_eval_id="a", session_risk=SessionRisk.HIJACKED, evaluation_score=90.0
        )
        eng.record_session(
            session_eval_id="b", session_risk=SessionRisk.HIJACKED, evaluation_score=70.0
        )
        assert "hijacked" in eng.analyze_session_distribution()

    def test_empty(self):
        assert _engine().analyze_session_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(session_gap_threshold=80.0)
        eng.record_session(session_eval_id="a", evaluation_score=60.0)
        eng.record_session(session_eval_id="b", evaluation_score=90.0)
        assert len(eng.identify_session_gaps()) == 1

    def test_sorted(self):
        eng = _engine(session_gap_threshold=80.0)
        eng.record_session(session_eval_id="a", evaluation_score=50.0)
        eng.record_session(session_eval_id="b", evaluation_score=30.0)
        assert len(eng.identify_session_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_session(session_eval_id="a", service="s1", evaluation_score=80.0)
        eng.record_session(session_eval_id="b", service="s2", evaluation_score=60.0)
        assert eng.rank_by_session()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_session() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(session_eval_id="t", analysis_score=float(v))
        assert eng.detect_session_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(session_eval_id="t", analysis_score=float(v))
        assert eng.detect_session_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_session_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_session(session_eval_id="t", evaluation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_session(session_eval_id="t")
        eng.add_analysis(session_eval_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_session(session_eval_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_session(session_eval_id="a")
        eng.record_session(session_eval_id="b")
        eng.add_analysis(session_eval_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1

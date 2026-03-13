"""Tests for ToilReductionIntelligence."""

from __future__ import annotations

from shieldops.analytics.toil_reduction_intelligence import (
    AutomationStatus,
    ToilReductionIntelligence,
    ToilSeverity,
    ToilType,
)


def _engine(**kw) -> ToilReductionIntelligence:
    return ToilReductionIntelligence(**kw)


class TestEnums:
    def test_toil_type_values(self):
        for v in ToilType:
            assert isinstance(v.value, str)

    def test_automation_status_values(self):
        for v in AutomationStatus:
            assert isinstance(v.value, str)

    def test_toil_severity_values(self):
        for v in ToilSeverity:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(team_id="t1")
        assert r.team_id == "t1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(team_id=f"t-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            team_id="t1",
            toil_type=ToilType.INTERRUPT_DRIVEN,
            automation_status=AutomationStatus.AUTOMATED,
            hours_spent=10.0,
            hours_saved=8.0,
        )
        assert r.hours_spent == 10.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(team_id="t1", hours_spent=10.0, hours_saved=5.0)
        a = eng.process(r.id)
        assert hasattr(a, "team_id")
        assert a.team_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_regression_detected(self):
        eng = _engine()
        r = eng.add_record(team_id="t1", hours_spent=10.0, hours_saved=-2.0)
        a = eng.process(r.id)
        assert a.regression_detected is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeToilReductionTrend:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", hours_spent=10.0, hours_saved=5.0)
        result = eng.compute_toil_reduction_trend()
        assert len(result) == 1
        assert result[0]["team_id"] == "t1"

    def test_empty(self):
        assert _engine().compute_toil_reduction_trend() == []


class TestDetectToilRegression:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", hours_spent=10.0, hours_saved=-3.0)
        result = eng.detect_toil_regression()
        assert len(result) == 1
        assert result[0]["regression_amount"] == 3.0

    def test_empty(self):
        assert _engine().detect_toil_regression() == []


class TestRankTeamsByToilBurden:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", hours_spent=20.0)
        eng.add_record(team_id="t2", hours_spent=40.0)
        result = eng.rank_teams_by_toil_burden()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_teams_by_toil_burden() == []

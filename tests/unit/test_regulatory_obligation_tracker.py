"""Tests for RegulatoryObligationTracker."""

from __future__ import annotations

from shieldops.compliance.regulatory_obligation_tracker import (
    ObligationStatus,
    ObligationType,
    PenaltyRisk,
    RegulatoryObligationTracker,
)


def _engine(**kw) -> RegulatoryObligationTracker:
    return RegulatoryObligationTracker(**kw)


class TestEnums:
    def test_obligation_status_values(self):
        for v in ObligationStatus:
            assert isinstance(v.value, str)

    def test_obligation_type_values(self):
        for v in ObligationType:
            assert isinstance(v.value, str)

    def test_penalty_risk_values(self):
        for v in PenaltyRisk:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(obligation_id="ob1")
        assert r.obligation_id == "ob1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(obligation_id=f"ob-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(obligation_id="ob1", completion_rate=75.0, days_to_deadline=10.0)
        a = eng.process(r.id)
        assert hasattr(a, "obligation_id")
        assert a.obligation_id == "ob1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(obligation_id="ob1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(obligation_id="ob1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(obligation_id="ob1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeObligationCompletionRate:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(obligation_id="ob1", completion_rate=80.0)
        result = eng.compute_obligation_completion_rate()
        assert len(result) == 1
        assert result[0]["obligation_id"] == "ob1"

    def test_empty(self):
        assert _engine().compute_obligation_completion_rate() == []


class TestDetectApproachingDeadlines:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            obligation_id="ob1",
            days_to_deadline=5.0,
            completion_rate=50.0,
        )
        result = eng.detect_approaching_deadlines()
        assert len(result) == 1
        assert result[0]["days_to_deadline"] == 5.0

    def test_empty(self):
        assert _engine().detect_approaching_deadlines() == []


class TestRankObligationsByPenaltyRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(obligation_id="ob1", penalty_amount=100000.0, completion_rate=50.0)
        eng.add_record(obligation_id="ob2", penalty_amount=50000.0, completion_rate=80.0)
        result = eng.rank_obligations_by_penalty_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_obligations_by_penalty_risk() == []

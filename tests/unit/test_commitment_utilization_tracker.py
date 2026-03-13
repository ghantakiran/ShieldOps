"""Tests for CommitmentUtilizationTracker."""

from __future__ import annotations

from shieldops.billing.commitment_utilization_tracker import (
    AdjustmentAction,
    CommitmentType,
    CommitmentUtilizationTracker,
    UtilizationLevel,
)


def _engine(**kw) -> CommitmentUtilizationTracker:
    return CommitmentUtilizationTracker(**kw)


class TestEnums:
    def test_commitment_type_values(self):
        for v in CommitmentType:
            assert isinstance(v.value, str)

    def test_utilization_level_values(self):
        for v in UtilizationLevel:
            assert isinstance(v.value, str)

    def test_adjustment_action_values(self):
        for v in AdjustmentAction:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(commitment_id="c1")
        assert r.commitment_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(commitment_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            commitment_id="c1",
            monthly_commitment=1000,
            utilization_pct=70,
        )
        a = eng.process(r.id)
        assert a.waste_amount == 300.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(utilization_pct=80)
        rpt = eng.generate_report()
        assert rpt.avg_utilization == 80.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_low_util_recommendation(self):
        eng = _engine()
        eng.add_record(utilization_level=UtilizationLevel.LOW)
        rpt = eng.generate_report()
        assert any("underutilized" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(commitment_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMeasureCommitmentUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            commitment_id="c1",
            utilization_pct=75,
        )
        result = eng.measure_commitment_utilization()
        assert len(result) == 1
        assert result[0]["avg_utilization"] == 75.0

    def test_empty(self):
        assert _engine().measure_commitment_utilization() == []


class TestDetectUnderutilizedCommitments:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            commitment_id="c1",
            utilization_pct=40,
            monthly_commitment=1000,
        )
        result = eng.detect_underutilized_commitments()
        assert len(result) == 1
        assert result[0]["monthly_waste"] == 600.0

    def test_high_util_excluded(self):
        eng = _engine()
        eng.add_record(utilization_pct=90)
        assert eng.detect_underutilized_commitments() == []


class TestRecommendCommitmentAdjustments:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            commitment_id="c1",
            utilization_pct=30,
        )
        result = eng.recommend_commitment_adjustments()
        assert result[0]["action"] == "terminate"

    def test_empty(self):
        assert _engine().recommend_commitment_adjustments() == []

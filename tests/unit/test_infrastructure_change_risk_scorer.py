"""Tests for InfrastructureChangeRiskScorer."""

from __future__ import annotations

from shieldops.changes.infrastructure_change_risk_scorer import (
    ChangeScope,
    InfrastructureChangeRiskScorer,
    RiskFactor,
    RollbackComplexity,
)


def _engine(**kw) -> InfrastructureChangeRiskScorer:
    return InfrastructureChangeRiskScorer(**kw)


class TestEnums:
    def test_change_scope_values(self):
        for v in ChangeScope:
            assert isinstance(v.value, str)

    def test_risk_factor_values(self):
        for v in RiskFactor:
            assert isinstance(v.value, str)

    def test_rollback_complexity_values(self):
        for v in RollbackComplexity:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(change_id="c1")
        assert r.change_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(change_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            change_id="c1",
            risk_score=80.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "change_id")
        assert a.is_high_risk is True

    def test_not_high_risk(self):
        eng = _engine()
        r = eng.record_item(
            change_id="c1",
            risk_score=30.0,
        )
        a = eng.process(r.id)
        assert a.is_high_risk is False

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(change_id="c1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(change_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(change_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeChangeRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(change_id="c1", risk_score=75.0)
        result = eng.compute_change_risk_score()
        assert len(result) == 1
        assert result[0]["avg_risk"] == 75.0

    def test_empty(self):
        r = _engine().compute_change_risk_score()
        assert r == []


class TestDetectHighRiskPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(change_id="c1", risk_score=90.0)
        result = eng.detect_high_risk_patterns()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().detect_high_risk_patterns()
        assert r == []


class TestRankChangesByRollbackComplexity:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            change_id="c1",
            rollback_complexity=(RollbackComplexity.COMPLEX),
        )
        eng.record_item(
            change_id="c2",
            rollback_complexity=(RollbackComplexity.TRIVIAL),
        )
        result = eng.rank_changes_by_rollback_complexity()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_changes_by_rollback_complexity()
        assert r == []

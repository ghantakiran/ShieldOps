"""Tests for shieldops.changes.change_intelligence — ChangeIntelligenceAnalyzer."""

from __future__ import annotations

from shieldops.changes.change_intelligence import (
    ChangeIntelligenceAnalyzer,
    ChangeOutcome,
    ChangeRecord,
    ChangeRiskLevel,
    RiskPrediction,
    SafetyGate,
    SafetyGateDecision,
)


def _engine(**kw) -> ChangeIntelligenceAnalyzer:
    return ChangeIntelligenceAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_risk_negligible(self):
        assert ChangeRiskLevel.NEGLIGIBLE == "negligible"

    def test_risk_low(self):
        assert ChangeRiskLevel.LOW == "low"

    def test_risk_moderate(self):
        assert ChangeRiskLevel.MODERATE == "moderate"

    def test_risk_high(self):
        assert ChangeRiskLevel.HIGH == "high"

    def test_risk_extreme(self):
        assert ChangeRiskLevel.EXTREME == "extreme"

    def test_outcome_success(self):
        assert ChangeOutcome.SUCCESS == "success"

    def test_outcome_degradation(self):
        assert ChangeOutcome.DEGRADATION == "degradation"

    def test_outcome_incident(self):
        assert ChangeOutcome.INCIDENT == "incident"

    def test_outcome_rollback(self):
        assert ChangeOutcome.ROLLBACK == "rollback"

    def test_outcome_unknown(self):
        assert ChangeOutcome.UNKNOWN == "unknown"

    def test_gate_pass(self):
        assert SafetyGate.PASS == "pass"  # noqa: S105

    def test_gate_conditional(self):
        assert SafetyGate.CONDITIONAL_PASS == "conditional_pass"  # noqa: S105

    def test_gate_hold(self):
        assert SafetyGate.HOLD == "hold"

    def test_gate_block(self):
        assert SafetyGate.BLOCK == "block"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_change_record_defaults(self):
        c = ChangeRecord()
        assert c.id
        assert c.outcome == ChangeOutcome.UNKNOWN
        assert c.risk_level == ChangeRiskLevel.LOW

    def test_risk_prediction_defaults(self):
        r = RiskPrediction()
        assert r.risk_score == 0.0

    def test_gate_decision_defaults(self):
        g = SafetyGateDecision()
        assert g.gate == SafetyGate.PASS


# ---------------------------------------------------------------------------
# record_change
# ---------------------------------------------------------------------------


class TestRecordChange:
    def test_basic_record(self):
        eng = _engine()
        c = eng.record_change(service="api", description="Update handler")
        assert c.service == "api"
        assert c.outcome == ChangeOutcome.UNKNOWN

    def test_unique_ids(self):
        eng = _engine()
        c1 = eng.record_change(service="a")
        c2 = eng.record_change(service="b")
        assert c1.id != c2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_change(service=f"svc-{i}")
        assert len(eng._changes) == 3

    def test_with_flags(self):
        eng = _engine()
        c = eng.record_change(
            has_db_migration=True,
            has_config_change=True,
            files_changed=25,
        )
        assert c.has_db_migration is True
        assert c.has_config_change is True


# ---------------------------------------------------------------------------
# get / list changes
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        c = eng.record_change(service="api")
        assert eng.get_change(c.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(service="a")
        eng.record_change(service="b")
        assert len(eng.list_changes()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_change(service="a")
        eng.record_change(service="b")
        results = eng.list_changes(service="a")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# predict_risk
# ---------------------------------------------------------------------------


class TestPredictRisk:
    def test_low_risk(self):
        eng = _engine()
        c = eng.record_change(files_changed=2, lines_changed=10)
        pred = eng.predict_risk(c.id)
        assert pred is not None
        assert pred.risk_level == ChangeRiskLevel.NEGLIGIBLE

    def test_high_risk(self):
        eng = _engine()
        c = eng.record_change(
            files_changed=30,
            lines_changed=2000,
            has_db_migration=True,
            has_config_change=True,
            is_rollback=True,
        )
        pred = eng.predict_risk(c.id)
        assert pred is not None
        assert pred.risk_level in (ChangeRiskLevel.HIGH, ChangeRiskLevel.EXTREME)

    def test_not_found(self):
        eng = _engine()
        assert eng.predict_risk("bad") is None

    def test_risk_factors_populated(self):
        eng = _engine()
        c = eng.record_change(has_db_migration=True, files_changed=25)
        pred = eng.predict_risk(c.id)
        assert pred is not None
        assert len(pred.risk_factors) >= 1


# ---------------------------------------------------------------------------
# evaluate_safety_gate
# ---------------------------------------------------------------------------


class TestEvaluateSafetyGate:
    def test_pass(self):
        eng = _engine()
        c = eng.record_change(files_changed=1, lines_changed=5)
        decision = eng.evaluate_safety_gate(c.id)
        assert decision is not None
        assert decision.gate == SafetyGate.PASS

    def test_block(self):
        eng = _engine()
        c = eng.record_change(
            files_changed=30,
            lines_changed=2000,
            has_db_migration=True,
            has_config_change=True,
            is_rollback=True,
        )
        decision = eng.evaluate_safety_gate(c.id)
        assert decision is not None
        assert decision.gate in (SafetyGate.HOLD, SafetyGate.BLOCK)

    def test_not_found(self):
        eng = _engine()
        assert eng.evaluate_safety_gate("bad") is None


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------


class TestRecordOutcome:
    def test_record(self):
        eng = _engine()
        c = eng.record_change(service="api")
        assert eng.record_outcome(c.id, ChangeOutcome.SUCCESS) is True
        assert c.outcome == ChangeOutcome.SUCCESS

    def test_not_found(self):
        eng = _engine()
        assert eng.record_outcome("bad", ChangeOutcome.SUCCESS) is False


# ---------------------------------------------------------------------------
# risk_factors / success_correlation / high_risk / stats
# ---------------------------------------------------------------------------


class TestRiskFactors:
    def test_factors(self):
        eng = _engine()
        eng.record_change(has_db_migration=True)
        eng.record_change(has_config_change=True)
        factors = eng.get_risk_factors()
        assert len(factors) >= 1


class TestSuccessCorrelation:
    def test_empty(self):
        eng = _engine()
        result = eng.get_success_correlation()
        assert result["total"] == 0

    def test_with_data(self):
        eng = _engine()
        c = eng.record_change(service="api")
        eng.record_outcome(c.id, ChangeOutcome.SUCCESS)
        result = eng.get_success_correlation()
        assert result["success_rate"] == 100.0


class TestHighRiskChanges:
    def test_none(self):
        eng = _engine()
        eng.record_change(files_changed=1)
        assert len(eng.get_high_risk_changes()) == 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_changes"] == 0

    def test_populated_stats(self):
        eng = _engine()
        c = eng.record_change(service="api")
        eng.record_outcome(c.id, ChangeOutcome.SUCCESS)
        stats = eng.get_stats()
        assert stats["total_changes"] == 1
        assert stats["success_rate"] == 100.0

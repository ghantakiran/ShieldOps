"""Tests for CostAnomalyRootCauseEngine."""

from __future__ import annotations

from shieldops.billing.cost_anomaly_root_cause_engine import (
    AnomalyType,
    CostAnomalyRootCauseEngine,
    EventCorrelation,
    RecurrenceRisk,
)


def _engine(**kw) -> CostAnomalyRootCauseEngine:
    return CostAnomalyRootCauseEngine(**kw)


class TestEnums:
    def test_anomaly_type_values(self):
        for v in AnomalyType:
            assert isinstance(v.value, str)

    def test_event_correlation_values(self):
        for v in EventCorrelation:
            assert isinstance(v.value, str)

    def test_recurrence_risk_values(self):
        for v in RecurrenceRisk:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(anomaly_id="a1")
        assert r.anomaly_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(anomaly_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            anomaly_id="a1",
            anomaly_amount=1500,
            baseline_amount=1000,
        )
        a = eng.process(r.id)
        assert a.deviation_pct == 50.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_baseline(self):
        eng = _engine()
        r = eng.add_record(baseline_amount=0)
        a = eng.process(r.id)
        assert a.deviation_pct == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(anomaly_amount=500)
        rpt = eng.generate_report()
        assert rpt.total_anomaly_amount == 500.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_recurring_recommendation(self):
        eng = _engine()
        eng.add_record(recurrence_risk=RecurrenceRisk.LIKELY)
        rpt = eng.generate_report()
        assert any("recur" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(anomaly_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestCorrelateAnomalyWithEvents:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(anomaly_amount=500)
        result = eng.correlate_anomaly_with_events()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().correlate_anomaly_with_events() == []


class TestDecomposeAnomalyContributors:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_name="s1", anomaly_amount=300)
        result = eng.decompose_anomaly_contributors()
        assert result[0]["service_name"] == "s1"

    def test_empty(self):
        assert _engine().decompose_anomaly_contributors() == []


class TestAssessAnomalyRecurrenceRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(anomaly_id="a1")
        result = eng.assess_anomaly_recurrence_risk()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().assess_anomaly_recurrence_risk() == []

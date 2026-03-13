"""Tests for EscalationPathOptimizer."""

from __future__ import annotations

from shieldops.incidents.escalation_path_optimizer import (
    AntipatternType,
    EscalationOutcome,
    EscalationPathOptimizer,
    PathType,
)


def _engine(**kw) -> EscalationPathOptimizer:
    return EscalationPathOptimizer(**kw)


class TestEnums:
    def test_escalation_outcome_values(self):
        for v in EscalationOutcome:
            assert isinstance(v.value, str)

    def test_path_type_values(self):
        for v in PathType:
            assert isinstance(v.value, str)

    def test_antipattern_type_values(self):
        for v in AntipatternType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(incident_id="inc-1")
        assert r.incident_id == "inc-1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(incident_id=f"inc-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            incident_id="inc-1",
            hops=3,
            total_time_min=45.0,
        )
        assert r.hops == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(incident_id="inc-1", hops=2)
        a = eng.process(r.id)
        assert hasattr(a, "incident_id")
        assert a.incident_id == "inc-1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1")
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
        eng.add_record(incident_id="inc-1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeEscalationEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            incident_id="inc-1",
            team="sre",
            hops=2,
        )
        result = eng.analyze_escalation_efficiency()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().analyze_escalation_efficiency()
        assert r == []


class TestDetectEscalationAntipatterns:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            incident_id="inc-1",
            antipattern_type=(AntipatternType.PINGPONG),
        )
        result = eng.detect_escalation_antipatterns()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().detect_escalation_antipatterns()
        assert r == []


class TestRecommendPathRestructuring:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            incident_id="inc-1",
            team="sre",
            escalation_outcome=(EscalationOutcome.RESOLVED),
        )
        result = eng.recommend_path_restructuring()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().recommend_path_restructuring()
        assert r == []

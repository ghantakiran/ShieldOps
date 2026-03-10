"""Tests for AutonomousIncidentCommander."""

from __future__ import annotations

from shieldops.operations.autonomous_incident_commander import (
    AutonomousIncidentCommander,
    CommandMode,
    EscalationTrigger,
    IncidentSeverity,
)


def _engine(**kw) -> AutonomousIncidentCommander:
    return AutonomousIncidentCommander(**kw)


class TestEnums:
    def test_command_mode_values(self):
        assert CommandMode.FULLY_AUTONOMOUS == "fully_autonomous"
        assert CommandMode.SEMI_AUTONOMOUS == "semi_autonomous"
        assert CommandMode.ADVISORY == "advisory"
        assert CommandMode.MANUAL == "manual"

    def test_incident_severity_values(self):
        assert IncidentSeverity.SEV1 == "sev1"
        assert IncidentSeverity.SEV2 == "sev2"
        assert IncidentSeverity.SEV3 == "sev3"
        assert IncidentSeverity.SEV4 == "sev4"

    def test_escalation_trigger_values(self):
        assert EscalationTrigger.TIMEOUT == "timeout"
        assert EscalationTrigger.THRESHOLD == "threshold"
        assert EscalationTrigger.COMPLEXITY == "complexity"
        assert EscalationTrigger.POLICY == "policy"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="inc-001",
            command_mode=CommandMode.FULLY_AUTONOMOUS,
            incident_severity=IncidentSeverity.SEV1,
            score=85.0,
            service="auth",
            team="sre",
        )
        assert r.name == "inc-001"
        assert r.command_mode == CommandMode.FULLY_AUTONOMOUS
        assert r.score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestAssessIncidentComplexity:
    def test_returns_sorted(self):
        eng = _engine()
        eng.record_item(
            name="low",
            incident_severity=IncidentSeverity.SEV4,
            score=90.0,
        )
        eng.record_item(
            name="high",
            incident_severity=IncidentSeverity.SEV1,
            score=10.0,
        )
        results = eng.assess_incident_complexity()
        assert len(results) == 2
        assert results[0]["name"] == "high"

    def test_empty(self):
        eng = _engine()
        assert eng.assess_incident_complexity() == []


class TestSelectResponseStrategy:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            command_mode=CommandMode.FULLY_AUTONOMOUS,
            score=90.0,
        )
        eng.record_item(
            name="b",
            command_mode=CommandMode.MANUAL,
            score=30.0,
        )
        result = eng.select_response_strategy()
        assert result["recommended_mode"] == "fully_autonomous"
        assert result["total_incidents"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.select_response_strategy()
        assert result["recommended_mode"] == "advisory"


class TestCoordinateResponseTeams:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", team="sre", score=80.0)
        eng.record_item(name="b", team="sre", score=70.0)
        eng.record_item(name="c", team="sec", score=90.0)
        results = eng.coordinate_response_teams()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["incident_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.coordinate_response_teams() == []

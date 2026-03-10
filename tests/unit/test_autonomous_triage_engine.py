"""Tests for AutonomousTriageEngine."""

from __future__ import annotations

from shieldops.incidents.autonomous_triage_engine import (
    AutonomousTriageEngine,
    TriageConfidence,
    TriageDecision,
    UrgencyLevel,
)


def _engine(**kw) -> AutonomousTriageEngine:
    return AutonomousTriageEngine(**kw)


class TestEnums:
    def test_triage_decision_values(self):
        assert TriageDecision.INVESTIGATE == "investigate"
        assert TriageDecision.ESCALATE == "escalate"
        assert TriageDecision.AUTO_RESOLVE == "auto_resolve"
        assert TriageDecision.DEFER == "defer"

    def test_urgency_level_values(self):
        assert UrgencyLevel.IMMEDIATE == "immediate"
        assert UrgencyLevel.URGENT == "urgent"
        assert UrgencyLevel.STANDARD == "standard"
        assert UrgencyLevel.LOW == "low"

    def test_triage_confidence_values(self):
        assert TriageConfidence.CERTAIN == "certain"
        assert TriageConfidence.HIGH == "high"
        assert TriageConfidence.MODERATE == "moderate"
        assert TriageConfidence.LOW == "low"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="triage-001",
            triage_decision=TriageDecision.ESCALATE,
            urgency_level=UrgencyLevel.IMMEDIATE,
            score=90.0,
            service="auth",
            team="sre",
        )
        assert r.name == "triage-001"
        assert r.triage_decision == TriageDecision.ESCALATE
        assert r.score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestAutoTriageIncident:
    def test_returns_sorted(self):
        eng = _engine()
        eng.add_record(
            name="high",
            urgency_level=UrgencyLevel.IMMEDIATE,
            score=80.0,
        )
        eng.add_record(
            name="low",
            urgency_level=UrgencyLevel.LOW,
            score=80.0,
        )
        results = eng.auto_triage_incident()
        assert results[0]["name"] == "high"
        assert results[0]["triage_score"] > results[1]["triage_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.auto_triage_incident() == []


class TestComputeTriageAccuracy:
    def test_with_data(self):
        eng = _engine(threshold=50.0)
        eng.add_record(
            name="a",
            triage_decision=TriageDecision.INVESTIGATE,
            score=80.0,
        )
        eng.add_record(
            name="b",
            triage_decision=TriageDecision.INVESTIGATE,
            score=30.0,
        )
        result = eng.compute_triage_accuracy()
        inv = result["by_decision"]["investigate"]
        assert inv["count"] == 2
        assert inv["accuracy"] == 50.0

    def test_empty(self):
        eng = _engine()
        result = eng.compute_triage_accuracy()
        assert result["total_triaged"] == 0


class TestDetectTriageDrift:
    def test_drift_detected(self):
        eng = _engine()
        for _ in range(2):
            eng.add_record(name="old", score=80.0)
        for _ in range(2):
            eng.add_record(name="new", score=40.0)
        result = eng.detect_triage_drift()
        assert result["drift_detected"] is True
        assert result["score_delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        eng.add_record(name="a", score=50.0)
        result = eng.detect_triage_drift()
        assert result["drift_detected"] is False

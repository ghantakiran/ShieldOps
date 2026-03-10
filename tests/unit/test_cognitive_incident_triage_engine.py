"""Tests for CognitiveIncidentTriageEngine."""

from __future__ import annotations

from shieldops.incidents.cognitive_incident_triage_engine import (
    CognitiveIncidentTriageEngine,
    SeverityRecommendation,
    TriageConfidence,
    TriageDecision,
)


def _engine(**kw) -> CognitiveIncidentTriageEngine:
    return CognitiveIncidentTriageEngine(**kw)


class TestEnums:
    def test_triage_decision(self):
        assert TriageDecision.AUTO_RESOLVE == "auto_resolve"

    def test_severity_recommendation(self):
        assert SeverityRecommendation.CRITICAL == "critical"

    def test_triage_confidence(self):
        assert TriageConfidence.DEFINITIVE == "definitive"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(incident_id="inc-1", service="api")
        assert rec.incident_id == "inc-1"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                incident_id=f"inc-{i}",
                service="svc",
            )
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        result = eng.process("inc-1")
        assert isinstance(result, dict)
        assert result["incident_id"] == "inc-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestRecommendTriage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        result = eng.recommend_triage("inc-1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(incident_id="inc-1", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0

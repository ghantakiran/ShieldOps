"""Tests for AutomatedIncidentClassifier."""

from __future__ import annotations

from shieldops.security.automated_incident_classifier import (
    AutomatedIncidentClassifier,
    ClassificationMethod,
    IncidentCategory,
    SeverityAssessment,
)


def _engine(**kw) -> AutomatedIncidentClassifier:
    return AutomatedIncidentClassifier(**kw)


class TestEnums:
    def test_cat_malware(self):
        assert IncidentCategory.MALWARE == "malware"

    def test_cat_phishing(self):
        assert IncidentCategory.PHISHING == "phishing"

    def test_cat_breach(self):
        assert IncidentCategory.DATA_BREACH == "data_breach"

    def test_cat_insider(self):
        assert IncidentCategory.INSIDER_THREAT == "insider_threat"

    def test_method_rule(self):
        assert ClassificationMethod.RULE_BASED == "rule_based"

    def test_method_ml(self):
        assert ClassificationMethod.ML_MODEL == "ml_model"

    def test_method_hybrid(self):
        assert ClassificationMethod.HYBRID == "hybrid"

    def test_method_manual(self):
        assert ClassificationMethod.MANUAL == "manual"

    def test_sev_critical(self):
        assert SeverityAssessment.CRITICAL == "critical"

    def test_sev_high(self):
        assert SeverityAssessment.HIGH == "high"

    def test_sev_medium(self):
        assert SeverityAssessment.MEDIUM == "medium"

    def test_sev_low(self):
        assert SeverityAssessment.LOW == "low"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            incident_id="i1",
            category=IncidentCategory.MALWARE,
            confidence_score=0.9,
        )
        assert r.incident_id == "i1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(incident_id=f"i-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(incident_id="i1", confidence_score=0.85)
        a = eng.process(r.id)
        assert a is not None
        assert a.incident_id == "i1"

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(incident_id="i1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(incident_id="i1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(incident_id="i1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestClassifyIncident:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            incident_id="i1",
            category=IncidentCategory.PHISHING,
            confidence_score=0.8,
        )
        result = eng.classify_incident()
        assert len(result) == 1
        assert result[0]["category"] == "phishing"

    def test_empty(self):
        assert _engine().classify_incident() == []


class TestComputeClassificationConfidence:
    def test_basic(self):
        eng = _engine()
        eng.add_record(incident_id="i1", confidence_score=0.9)
        result = eng.compute_classification_confidence()
        assert result["overall_confidence"] == 0.9

    def test_empty(self):
        result = _engine().compute_classification_confidence()
        assert result["overall_confidence"] == 0.0


class TestDetectMisclassifications:
    def test_basic(self):
        eng = _engine(confidence_threshold=0.8)
        eng.add_record(
            incident_id="i1",
            confidence_score=0.3,
            is_verified=False,
        )
        result = eng.detect_misclassifications()
        assert len(result) == 1
        assert result[0]["misclassification_risk"] > 0

    def test_empty(self):
        assert _engine().detect_misclassifications() == []

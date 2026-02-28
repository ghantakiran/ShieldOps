"""Tests for shieldops.incidents.severity_validator — IncidentSeverityValidator."""

from __future__ import annotations

from shieldops.incidents.severity_validator import (
    IncidentSeverityValidator,
    SeverityCriteria,
    SeverityLevel,
    SeverityValidationRecord,
    SeverityValidatorReport,
    ValidationCriterion,
    ValidationOutcome,
)


def _engine(**kw) -> IncidentSeverityValidator:
    return IncidentSeverityValidator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SeverityLevel (5)
    def test_level_sev1(self):
        assert SeverityLevel.SEV1 == "sev1"

    def test_level_sev2(self):
        assert SeverityLevel.SEV2 == "sev2"

    def test_level_sev3(self):
        assert SeverityLevel.SEV3 == "sev3"

    def test_level_sev4(self):
        assert SeverityLevel.SEV4 == "sev4"

    def test_level_sev5(self):
        assert SeverityLevel.SEV5 == "sev5"

    # ValidationOutcome (5)
    def test_outcome_correct(self):
        assert ValidationOutcome.CORRECT == "correct"

    def test_outcome_over_classified(self):
        assert ValidationOutcome.OVER_CLASSIFIED == "over_classified"

    def test_outcome_under_classified(self):
        assert ValidationOutcome.UNDER_CLASSIFIED == "under_classified"

    def test_outcome_needs_review(self):
        assert ValidationOutcome.NEEDS_REVIEW == "needs_review"

    def test_outcome_inconclusive(self):
        assert ValidationOutcome.INCONCLUSIVE == "inconclusive"

    # SeverityCriteria (5)
    def test_criteria_user_impact(self):
        assert SeverityCriteria.USER_IMPACT == "user_impact"

    def test_criteria_revenue_impact(self):
        assert SeverityCriteria.REVENUE_IMPACT == "revenue_impact"

    def test_criteria_data_loss(self):
        assert SeverityCriteria.DATA_LOSS == "data_loss"

    def test_criteria_service_degradation(self):
        assert SeverityCriteria.SERVICE_DEGRADATION == "service_degradation"

    def test_criteria_security_breach(self):
        assert SeverityCriteria.SECURITY_BREACH == "security_breach"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_severity_validation_record_defaults(self):
        r = SeverityValidationRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.assigned_severity == SeverityLevel.SEV3
        assert r.validated_severity == SeverityLevel.SEV3
        assert r.outcome == ValidationOutcome.CORRECT
        assert r.criteria == SeverityCriteria.SERVICE_DEGRADATION
        assert r.accuracy_score == 100.0
        assert r.validator_id == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_validation_criterion_defaults(self):
        r = ValidationCriterion()
        assert r.id
        assert r.criteria == SeverityCriteria.SERVICE_DEGRADATION
        assert r.severity_level == SeverityLevel.SEV3
        assert r.threshold_description == ""
        assert r.weight == 1.0
        assert r.active is True
        assert r.created_at > 0

    def test_severity_validator_report_defaults(self):
        r = SeverityValidatorReport()
        assert r.total_validations == 0
        assert r.total_criteria == 0
        assert r.accuracy_pct == 0.0
        assert r.by_outcome == {}
        assert r.by_severity == {}
        assert r.misclassified_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_validation
# -------------------------------------------------------------------


class TestRecordValidation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_validation(
            "INC-001",
            assigned_severity=SeverityLevel.SEV2,
            outcome=ValidationOutcome.CORRECT,
        )
        assert r.incident_id == "INC-001"
        assert r.assigned_severity == SeverityLevel.SEV2
        assert r.outcome == ValidationOutcome.CORRECT

    def test_with_validator(self):
        eng = _engine()
        r = eng.record_validation("INC-002", validator_id="user-42", accuracy_score=90.0)
        assert r.validator_id == "user-42"
        assert r.accuracy_score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(f"INC-{i:03d}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_validation
# -------------------------------------------------------------------


class TestGetValidation:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation("INC-001")
        assert eng.get_validation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None


# -------------------------------------------------------------------
# list_validations
# -------------------------------------------------------------------


class TestListValidations:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation("INC-001")
        eng.record_validation("INC-002")
        assert len(eng.list_validations()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_validation("INC-001")
        eng.record_validation("INC-002")
        results = eng.list_validations(incident_id="INC-001")
        assert len(results) == 1

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_validation("INC-001", outcome=ValidationOutcome.CORRECT)
        eng.record_validation("INC-002", outcome=ValidationOutcome.OVER_CLASSIFIED)
        results = eng.list_validations(outcome=ValidationOutcome.OVER_CLASSIFIED)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_criterion
# -------------------------------------------------------------------


class TestAddCriterion:
    def test_basic(self):
        eng = _engine()
        c = eng.add_criterion(
            criteria=SeverityCriteria.USER_IMPACT,
            severity_level=SeverityLevel.SEV1,
            threshold_description=">50% users affected",
            weight=2.0,
        )
        assert c.criteria == SeverityCriteria.USER_IMPACT
        assert c.severity_level == SeverityLevel.SEV1
        assert c.weight == 2.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(4):
            eng.add_criterion()
        assert len(eng._criteria) == 2


# -------------------------------------------------------------------
# analyze_validation_accuracy
# -------------------------------------------------------------------


class TestAnalyzeValidationAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation("INC-001", outcome=ValidationOutcome.CORRECT, validator_id="v1")
        eng.record_validation(
            "INC-002", outcome=ValidationOutcome.OVER_CLASSIFIED, validator_id="v1"
        )
        result = eng.analyze_validation_accuracy("v1")
        assert result["validator_id"] == "v1"
        assert result["total_validations"] == 2
        assert result["accuracy_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_validation_accuracy("unknown")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_misclassified_incidents
# -------------------------------------------------------------------


class TestIdentifyMisclassifiedIncidents:
    def test_with_misclassified(self):
        eng = _engine()
        eng.record_validation(
            "INC-001", outcome=ValidationOutcome.OVER_CLASSIFIED, accuracy_score=60.0
        )
        eng.record_validation("INC-002", outcome=ValidationOutcome.CORRECT)
        results = eng.identify_misclassified_incidents()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_misclassified_incidents() == []


# -------------------------------------------------------------------
# rank_by_accuracy_score
# -------------------------------------------------------------------


class TestRankByAccuracyScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation("INC-001", accuracy_score=95.0)
        eng.record_validation("INC-002", accuracy_score=70.0)
        results = eng.rank_by_accuracy_score()
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["accuracy_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_accuracy_score() == []


# -------------------------------------------------------------------
# detect_classification_bias
# -------------------------------------------------------------------


class TestDetectClassificationBias:
    def test_bias_detected(self):
        eng = _engine()
        # More than 20% over-classified for SEV2
        for _ in range(8):
            eng.record_validation(
                "INC-x", assigned_severity=SeverityLevel.SEV2, outcome=ValidationOutcome.CORRECT
            )
        for _ in range(3):
            eng.record_validation(
                "INC-y",
                assigned_severity=SeverityLevel.SEV2,
                outcome=ValidationOutcome.OVER_CLASSIFIED,
            )
        results = eng.detect_classification_bias()
        assert len(results) >= 1
        assert results[0]["bias_detected"] is True

    def test_no_bias(self):
        eng = _engine()
        eng.record_validation(
            "INC-001", assigned_severity=SeverityLevel.SEV3, outcome=ValidationOutcome.CORRECT
        )
        assert eng.detect_classification_bias() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation("INC-001", outcome=ValidationOutcome.CORRECT)
        eng.record_validation("INC-002", outcome=ValidationOutcome.OVER_CLASSIFIED)
        eng.add_criterion()
        report = eng.generate_report()
        assert report.total_validations == 2
        assert report.total_criteria == 1
        assert report.by_outcome != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_validations == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_validation("INC-001")
        eng.add_criterion()
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._criteria) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_validations"] == 0
        assert stats["total_criteria"] == 0
        assert stats["outcome_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_validation("INC-001", outcome=ValidationOutcome.CORRECT)
        eng.record_validation("INC-002", outcome=ValidationOutcome.OVER_CLASSIFIED)
        eng.add_criterion()
        stats = eng.get_stats()
        assert stats["total_validations"] == 2
        assert stats["total_criteria"] == 1
        assert stats["unique_incidents"] == 2

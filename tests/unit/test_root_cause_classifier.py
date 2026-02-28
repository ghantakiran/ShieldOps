"""Tests for shieldops.incidents.root_cause_classifier — IncidentRootCauseClassifier."""

from __future__ import annotations

from shieldops.incidents.root_cause_classifier import (
    CausePattern,
    ClassificationConfidence,
    ClassificationMethod,
    IncidentRootCauseClassifier,
    RootCauseCategory,
    RootCauseRecord,
    RootCauseReport,
)


def _engine(**kw) -> IncidentRootCauseClassifier:
    return IncidentRootCauseClassifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RootCauseCategory (5)
    def test_category_code_defect(self):
        assert RootCauseCategory.CODE_DEFECT == "code_defect"

    def test_category_config_error(self):
        assert RootCauseCategory.CONFIGURATION_ERROR == "configuration_error"

    def test_category_infra_failure(self):
        assert RootCauseCategory.INFRASTRUCTURE_FAILURE == "infrastructure_failure"

    def test_category_capacity(self):
        assert RootCauseCategory.CAPACITY_ISSUE == "capacity_issue"

    def test_category_dependency(self):
        assert RootCauseCategory.DEPENDENCY_FAILURE == "dependency_failure"

    # ClassificationConfidence (5)
    def test_confidence_high(self):
        assert ClassificationConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert ClassificationConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert ClassificationConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert ClassificationConfidence.SPECULATIVE == "speculative"

    def test_confidence_unclassified(self):
        assert ClassificationConfidence.UNCLASSIFIED == "unclassified"

    # ClassificationMethod (5)
    def test_method_automated(self):
        assert ClassificationMethod.AUTOMATED == "automated"

    def test_method_manual(self):
        assert ClassificationMethod.MANUAL == "manual"

    def test_method_hybrid(self):
        assert ClassificationMethod.HYBRID == "hybrid"

    def test_method_ml_assisted(self):
        assert ClassificationMethod.ML_ASSISTED == "ml_assisted"

    def test_method_pattern_matched(self):
        assert ClassificationMethod.PATTERN_MATCHED == "pattern_matched"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_root_cause_record_defaults(self):
        r = RootCauseRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.category == RootCauseCategory.CODE_DEFECT
        assert r.confidence == ClassificationConfidence.MODERATE
        assert r.method == ClassificationMethod.AUTOMATED
        assert r.root_cause_description == ""
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_cause_pattern_defaults(self):
        p = CausePattern()
        assert p.id
        assert p.category == RootCauseCategory.CODE_DEFECT
        assert p.pattern_name == ""
        assert p.occurrence_count == 0
        assert p.avg_resolution_minutes == 0.0
        assert p.created_at > 0

    def test_report_defaults(self):
        r = RootCauseReport()
        assert r.total_records == 0
        assert r.total_patterns == 0
        assert r.classification_accuracy_pct == 0.0
        assert r.by_category == {}
        assert r.by_confidence == {}
        assert r.by_method == {}
        assert r.top_causes == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_classification
# -------------------------------------------------------------------


class TestRecordClassification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_classification(
            "inc-001",
            category=(RootCauseCategory.CODE_DEFECT),
            confidence=ClassificationConfidence.HIGH,
        )
        assert r.incident_id == "inc-001"
        assert r.category == RootCauseCategory.CODE_DEFECT
        assert r.confidence == ClassificationConfidence.HIGH

    def test_with_service(self):
        eng = _engine()
        r = eng.record_classification("inc-002", service="api-gateway")
        assert r.service == "api-gateway"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_classification(f"inc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_classification
# -------------------------------------------------------------------


class TestGetClassification:
    def test_found(self):
        eng = _engine()
        r = eng.record_classification("inc-001")
        assert eng.get_classification(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_classification("nonexistent") is None


# -------------------------------------------------------------------
# list_classifications
# -------------------------------------------------------------------


class TestListClassifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_classification("inc-001")
        eng.record_classification("inc-002")
        assert len(eng.list_classifications()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_classification(
            "inc-001",
            category=(RootCauseCategory.CODE_DEFECT),
        )
        eng.record_classification(
            "inc-002",
            category=(RootCauseCategory.CAPACITY_ISSUE),
        )
        results = eng.list_classifications(category=RootCauseCategory.CODE_DEFECT)
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_classification(
            "inc-001",
            confidence=ClassificationConfidence.HIGH,
        )
        eng.record_classification(
            "inc-002",
            confidence=ClassificationConfidence.LOW,
        )
        results = eng.list_classifications(confidence=ClassificationConfidence.HIGH)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_cause_pattern
# -------------------------------------------------------------------


class TestAddCausePattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_cause_pattern(
            pattern_name="null-pointer",
            occurrence_count=12,
            avg_resolution_minutes=45.0,
        )
        assert p.pattern_name == "null-pointer"
        assert p.occurrence_count == 12
        assert p.avg_resolution_minutes == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_cause_pattern(pattern_name=f"pat-{i}")
        assert len(eng._patterns) == 2


# -------------------------------------------------------------------
# analyze_causes_by_category
# -------------------------------------------------------------------


class TestAnalyzeCausesByCategory:
    def test_with_data(self):
        eng = _engine()
        eng.record_classification(
            "inc-1",
            category=(RootCauseCategory.CODE_DEFECT),
        )
        eng.record_classification(
            "inc-2",
            category=(RootCauseCategory.CODE_DEFECT),
        )
        eng.record_classification(
            "inc-3",
            category=(RootCauseCategory.CAPACITY_ISSUE),
        )
        results = eng.analyze_causes_by_category()
        assert results[0]["category"] == "code_defect"
        assert results[0]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_causes_by_category() == []


# -------------------------------------------------------------------
# identify_low_confidence_classifications
# -------------------------------------------------------------------


class TestIdentifyLowConfidence:
    def test_with_low_confidence(self):
        eng = _engine()
        eng.record_classification(
            "inc-1",
            confidence=ClassificationConfidence.LOW,
        )
        eng.record_classification(
            "inc-2",
            confidence=ClassificationConfidence.HIGH,
        )
        results = eng.identify_low_confidence_classifications()
        assert len(results) == 1
        assert results[0]["confidence"] == "low"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_classifications() == []


# -------------------------------------------------------------------
# rank_by_occurrence
# -------------------------------------------------------------------


class TestRankByOccurrence:
    def test_with_data(self):
        eng = _engine()
        eng.add_cause_pattern(
            pattern_name="oom",
            occurrence_count=20,
        )
        eng.add_cause_pattern(
            pattern_name="timeout",
            occurrence_count=5,
        )
        results = eng.rank_by_occurrence()
        assert results[0]["occurrence_count"] == 20

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_occurrence() == []


# -------------------------------------------------------------------
# detect_classification_trends
# -------------------------------------------------------------------


class TestDetectClassificationTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(4):
            eng.record_classification(
                "inc-x",
                category=(RootCauseCategory.CODE_DEFECT),
            )
        eng.record_classification(
            "inc-y",
            category=(RootCauseCategory.CAPACITY_ISSUE),
        )
        results = eng.detect_classification_trends()
        assert len(results) == 1
        assert results[0]["category"] == "code_defect"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_classification_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_confidence_pct=70.0)
        eng.record_classification(
            "inc-1",
            confidence=ClassificationConfidence.HIGH,
        )
        eng.record_classification(
            "inc-2",
            confidence=ClassificationConfidence.LOW,
        )
        eng.add_cause_pattern(pattern_name="pat-1")
        report = eng.generate_report()
        assert isinstance(report, RootCauseReport)
        assert report.total_records == 2
        assert report.total_patterns == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable limits" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_classification("inc-1")
        eng.add_cause_pattern(pattern_name="pat-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_classification(
            "inc-1",
            category=(RootCauseCategory.CODE_DEFECT),
        )
        eng.record_classification(
            "inc-2",
            category=(RootCauseCategory.CAPACITY_ISSUE),
        )
        eng.add_cause_pattern(pattern_name="pat-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_patterns"] == 1
        assert stats["unique_services"] == 1

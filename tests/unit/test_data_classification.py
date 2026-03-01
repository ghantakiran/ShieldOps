"""Tests for shieldops.security.data_classification — DataClassificationEngine."""

from __future__ import annotations

from shieldops.security.data_classification import (
    ClassificationRecord,
    ClassificationRule,
    ClassificationStatus,
    DataCategory,
    DataClassificationEngine,
    DataClassificationReport,
    DataSensitivity,
)


def _engine(**kw) -> DataClassificationEngine:
    return DataClassificationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_sensitivity_top_secret(self):
        assert DataSensitivity.TOP_SECRET == "top_secret"  # noqa: S105

    def test_sensitivity_confidential(self):
        assert DataSensitivity.CONFIDENTIAL == "confidential"

    def test_sensitivity_internal(self):
        assert DataSensitivity.INTERNAL == "internal"

    def test_sensitivity_public(self):
        assert DataSensitivity.PUBLIC == "public"

    def test_sensitivity_unclassified(self):
        assert DataSensitivity.UNCLASSIFIED == "unclassified"

    def test_status_classified(self):
        assert ClassificationStatus.CLASSIFIED == "classified"

    def test_status_pending(self):
        assert ClassificationStatus.PENDING == "pending"

    def test_status_needs_review(self):
        assert ClassificationStatus.NEEDS_REVIEW == "needs_review"

    def test_status_reclassified(self):
        assert ClassificationStatus.RECLASSIFIED == "reclassified"

    def test_status_exempt(self):
        assert ClassificationStatus.EXEMPT == "exempt"

    def test_category_pii(self):
        assert DataCategory.PII == "pii"

    def test_category_financial(self):
        assert DataCategory.FINANCIAL == "financial"

    def test_category_healthcare(self):
        assert DataCategory.HEALTHCARE == "healthcare"

    def test_category_credentials(self):
        assert DataCategory.CREDENTIALS == "credentials"

    def test_category_operational(self):
        assert DataCategory.OPERATIONAL == "operational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_classification_record_defaults(self):
        r = ClassificationRecord()
        assert r.id
        assert r.classification_id == ""
        assert r.data_sensitivity == DataSensitivity.UNCLASSIFIED
        assert r.classification_status == ClassificationStatus.PENDING
        assert r.data_category == DataCategory.OPERATIONAL
        assert r.coverage_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_classification_rule_defaults(self):
        r = ClassificationRule()
        assert r.id
        assert r.classification_id == ""
        assert r.data_sensitivity == DataSensitivity.UNCLASSIFIED
        assert r.value == 0.0
        assert r.threshold == 0.0
        assert r.breached is False
        assert r.description == ""
        assert r.created_at > 0

    def test_data_classification_report_defaults(self):
        r = DataClassificationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.unclassified_data == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_sensitivity == {}
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.top_unclassified == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_classification
# ---------------------------------------------------------------------------


class TestRecordClassification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_classification(
            classification_id="CLS-001",
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            classification_status=ClassificationStatus.CLASSIFIED,
            data_category=DataCategory.PII,
            coverage_pct=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.classification_id == "CLS-001"
        assert r.data_sensitivity == DataSensitivity.CONFIDENTIAL
        assert r.classification_status == ClassificationStatus.CLASSIFIED
        assert r.data_category == DataCategory.PII
        assert r.coverage_pct == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_classification(classification_id=f"CLS-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_classification
# ---------------------------------------------------------------------------


class TestGetClassification:
    def test_found(self):
        eng = _engine()
        r = eng.record_classification(
            classification_id="CLS-001",
            classification_status=ClassificationStatus.NEEDS_REVIEW,
        )
        result = eng.get_classification(r.id)
        assert result is not None
        assert result.classification_status == ClassificationStatus.NEEDS_REVIEW

    def test_not_found(self):
        eng = _engine()
        assert eng.get_classification("nonexistent") is None


# ---------------------------------------------------------------------------
# list_classifications
# ---------------------------------------------------------------------------


class TestListClassifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001")
        eng.record_classification(classification_id="CLS-002")
        assert len(eng.list_classifications()) == 2

    def test_filter_by_sensitivity(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            data_sensitivity=DataSensitivity.TOP_SECRET,
        )
        eng.record_classification(
            classification_id="CLS-002",
            data_sensitivity=DataSensitivity.UNCLASSIFIED,
        )
        results = eng.list_classifications(sensitivity=DataSensitivity.TOP_SECRET)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            classification_status=ClassificationStatus.CLASSIFIED,
        )
        eng.record_classification(
            classification_id="CLS-002",
            classification_status=ClassificationStatus.PENDING,
        )
        results = eng.list_classifications(status=ClassificationStatus.CLASSIFIED)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001", service="api")
        eng.record_classification(classification_id="CLS-002", service="web")
        results = eng.list_classifications(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001", team="sre")
        eng.record_classification(classification_id="CLS-002", team="platform")
        results = eng.list_classifications(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_classification(classification_id=f"CLS-{i}")
        assert len(eng.list_classifications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            classification_id="CLS-001",
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Sensitivity check passed",
        )
        assert r.classification_id == "CLS-001"
        assert r.data_sensitivity == DataSensitivity.CONFIDENTIAL
        assert r.value == 75.0
        assert r.threshold == 80.0
        assert r.breached is False
        assert r.description == "Sensitivity check passed"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(classification_id=f"CLS-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_classification_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeClassificationCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            coverage_pct=80.0,
        )
        eng.record_classification(
            classification_id="CLS-002",
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            coverage_pct=100.0,
        )
        result = eng.analyze_classification_coverage()
        assert "confidential" in result
        assert result["confidential"]["count"] == 2
        assert result["confidential"]["avg_coverage_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_classification_coverage() == {}


# ---------------------------------------------------------------------------
# identify_unclassified_data
# ---------------------------------------------------------------------------


class TestIdentifyUnclassifiedData:
    def test_detects_pending(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            classification_status=ClassificationStatus.PENDING,
        )
        eng.record_classification(
            classification_id="CLS-002",
            classification_status=ClassificationStatus.CLASSIFIED,
        )
        results = eng.identify_unclassified_data()
        assert len(results) == 1
        assert results[0]["classification_id"] == "CLS-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unclassified_data() == []


# ---------------------------------------------------------------------------
# rank_by_sensitivity
# ---------------------------------------------------------------------------


class TestRankBySensitivity:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001", service="api", coverage_pct=95.0)
        eng.record_classification(classification_id="CLS-002", service="api", coverage_pct=85.0)
        eng.record_classification(classification_id="CLS-003", service="web", coverage_pct=50.0)
        results = eng.rank_by_sensitivity()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_coverage_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_sensitivity() == []


# ---------------------------------------------------------------------------
# detect_classification_drift
# ---------------------------------------------------------------------------


class TestDetectClassificationDrift:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_rule(classification_id="CLS-001", value=val)
        result = eng.detect_classification_drift()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_rule(classification_id="CLS-001", value=val)
        result = eng.detect_classification_drift()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_classification_drift()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            classification_status=ClassificationStatus.PENDING,
            coverage_pct=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DataClassificationReport)
        assert report.total_records == 1
        assert report.unclassified_data == 1
        assert report.avg_coverage_pct == 50.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_classification(classification_id="CLS-001")
        eng.add_rule(classification_id="CLS-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["sensitivity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_classification(
            classification_id="CLS-001",
            data_sensitivity=DataSensitivity.TOP_SECRET,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_classifications"] == 1
        assert "top_secret" in stats["sensitivity_distribution"]

"""Tests for shieldops.observability.log_quality — LogQualityAnalyzer."""

from __future__ import annotations

from shieldops.observability.log_quality import (
    LogIssue,
    LogIssueType,
    LogQualityAnalyzer,
    LogQualityDimension,
    LogQualityLevel,
    LogQualityRecord,
    LogQualityReport,
)


def _engine(**kw) -> LogQualityAnalyzer:
    return LogQualityAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_structure(self):
        assert LogQualityDimension.STRUCTURE == "structure"

    def test_dimension_completeness(self):
        assert LogQualityDimension.COMPLETENESS == "completeness"

    def test_dimension_consistency(self):
        assert LogQualityDimension.CONSISTENCY == "consistency"

    def test_dimension_searchability(self):
        assert LogQualityDimension.SEARCHABILITY == "searchability"

    def test_dimension_context(self):
        assert LogQualityDimension.CONTEXT == "context"

    def test_level_excellent(self):
        assert LogQualityLevel.EXCELLENT == "excellent"

    def test_level_good(self):
        assert LogQualityLevel.GOOD == "good"

    def test_level_acceptable(self):
        assert LogQualityLevel.ACCEPTABLE == "acceptable"

    def test_level_poor(self):
        assert LogQualityLevel.POOR == "poor"

    def test_level_unusable(self):
        assert LogQualityLevel.UNUSABLE == "unusable"

    def test_issue_unstructured(self):
        assert LogIssueType.UNSTRUCTURED == "unstructured"

    def test_issue_missing_fields(self):
        assert LogIssueType.MISSING_FIELDS == "missing_fields"

    def test_issue_inconsistent_format(self):
        assert LogIssueType.INCONSISTENT_FORMAT == "inconsistent_format"

    def test_issue_high_noise(self):
        assert LogIssueType.HIGH_NOISE == "high_noise"

    def test_issue_pii_exposure(self):
        assert LogIssueType.PII_EXPOSURE == "pii_exposure"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_log_quality_record_defaults(self):
        r = LogQualityRecord()
        assert r.id
        assert r.service_id == ""
        assert r.log_quality_dimension == LogQualityDimension.STRUCTURE
        assert r.log_quality_level == LogQualityLevel.ACCEPTABLE
        assert r.log_issue_type == LogIssueType.UNSTRUCTURED
        assert r.quality_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_log_issue_defaults(self):
        i = LogIssue()
        assert i.id
        assert i.issue_name == ""
        assert i.log_quality_dimension == LogQualityDimension.STRUCTURE
        assert i.quality_threshold == 0.0
        assert i.avg_quality_score == 0.0
        assert i.description == ""
        assert i.created_at > 0

    def test_log_quality_report_defaults(self):
        r = LogQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_issues == 0
        assert r.poor_quality_logs == 0
        assert r.avg_quality_score == 0.0
        assert r.by_dimension == {}
        assert r.by_level == {}
        assert r.by_issue_type == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_quality
# ---------------------------------------------------------------------------


class TestRecordQuality:
    def test_basic(self):
        eng = _engine()
        r = eng.record_quality(
            service_id="svc-001",
            log_quality_dimension=LogQualityDimension.COMPLETENESS,
            log_quality_level=LogQualityLevel.GOOD,
            log_issue_type=LogIssueType.MISSING_FIELDS,
            quality_score=85.0,
            team="platform",
        )
        assert r.service_id == "svc-001"
        assert r.log_quality_dimension == LogQualityDimension.COMPLETENESS
        assert r.log_quality_level == LogQualityLevel.GOOD
        assert r.log_issue_type == LogIssueType.MISSING_FIELDS
        assert r.quality_score == 85.0
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_quality(service_id=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_quality
# ---------------------------------------------------------------------------


class TestGetQuality:
    def test_found(self):
        eng = _engine()
        r = eng.record_quality(
            service_id="svc-001",
            log_quality_level=LogQualityLevel.EXCELLENT,
        )
        result = eng.get_quality(r.id)
        assert result is not None
        assert result.log_quality_level == LogQualityLevel.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_quality("nonexistent") is None


# ---------------------------------------------------------------------------
# list_qualities
# ---------------------------------------------------------------------------


class TestListQualities:
    def test_list_all(self):
        eng = _engine()
        eng.record_quality(service_id="svc-001")
        eng.record_quality(service_id="svc-002")
        assert len(eng.list_qualities()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_dimension=LogQualityDimension.STRUCTURE,
        )
        eng.record_quality(
            service_id="svc-002",
            log_quality_dimension=LogQualityDimension.CONTEXT,
        )
        results = eng.list_qualities(dimension=LogQualityDimension.STRUCTURE)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_level=LogQualityLevel.EXCELLENT,
        )
        eng.record_quality(
            service_id="svc-002",
            log_quality_level=LogQualityLevel.POOR,
        )
        results = eng.list_qualities(level=LogQualityLevel.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_quality(service_id="svc-001", team="sre")
        eng.record_quality(service_id="svc-002", team="platform")
        results = eng.list_qualities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_quality(service_id=f"svc-{i}")
        assert len(eng.list_qualities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_issue
# ---------------------------------------------------------------------------


class TestAddIssue:
    def test_basic(self):
        eng = _engine()
        i = eng.add_issue(
            issue_name="missing-trace-id",
            log_quality_dimension=LogQualityDimension.COMPLETENESS,
            quality_threshold=0.8,
            avg_quality_score=65.0,
            description="Missing trace ID in logs",
        )
        assert i.issue_name == "missing-trace-id"
        assert i.log_quality_dimension == LogQualityDimension.COMPLETENESS
        assert i.quality_threshold == 0.8
        assert i.avg_quality_score == 65.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_issue(issue_name=f"issue-{i}")
        assert len(eng._issues) == 2


# ---------------------------------------------------------------------------
# analyze_log_quality
# ---------------------------------------------------------------------------


class TestAnalyzeLogQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_dimension=LogQualityDimension.STRUCTURE,
            quality_score=90.0,
        )
        eng.record_quality(
            service_id="svc-002",
            log_quality_dimension=LogQualityDimension.STRUCTURE,
            quality_score=80.0,
        )
        result = eng.analyze_log_quality()
        assert "structure" in result
        assert result["structure"]["count"] == 2
        assert result["structure"]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_log_quality() == {}


# ---------------------------------------------------------------------------
# identify_poor_quality_logs
# ---------------------------------------------------------------------------


class TestIdentifyPoorQualityLogs:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_level=LogQualityLevel.POOR,
            quality_score=20.0,
        )
        eng.record_quality(
            service_id="svc-002",
            log_quality_level=LogQualityLevel.EXCELLENT,
        )
        results = eng.identify_poor_quality_logs()
        assert len(results) == 1
        assert results[0]["service_id"] == "svc-001"

    def test_detects_unusable(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_level=LogQualityLevel.UNUSABLE,
        )
        results = eng.identify_poor_quality_logs()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_quality_logs() == []


# ---------------------------------------------------------------------------
# rank_by_quality_score
# ---------------------------------------------------------------------------


class TestRankByQualityScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_quality(service_id="svc-001", team="sre", quality_score=90.0)
        eng.record_quality(service_id="svc-002", team="sre", quality_score=80.0)
        eng.record_quality(service_id="svc-003", team="platform", quality_score=70.0)
        results = eng.rank_by_quality_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality_score() == []


# ---------------------------------------------------------------------------
# detect_quality_regression
# ---------------------------------------------------------------------------


class TestDetectQualityRegression:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_issue(issue_name="i", avg_quality_score=s)
        result = eng.detect_quality_regression()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_issue(issue_name="i", avg_quality_score=s)
        result = eng.detect_quality_regression()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_quality_regression()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_level=LogQualityLevel.POOR,
            log_quality_dimension=LogQualityDimension.STRUCTURE,
            quality_score=30.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, LogQualityReport)
        assert report.total_records == 1
        assert report.poor_quality_logs == 1
        assert report.avg_quality_score == 30.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "below threshold" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_quality(service_id="svc-001")
        eng.add_issue(issue_name="i1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._issues) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_issues"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_quality(
            service_id="svc-001",
            log_quality_dimension=LogQualityDimension.STRUCTURE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "structure" in stats["dimension_distribution"]

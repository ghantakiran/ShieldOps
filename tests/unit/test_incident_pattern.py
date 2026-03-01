"""Tests for shieldops.incidents.incident_pattern — IncidentPatternDetector."""

from __future__ import annotations

from shieldops.incidents.incident_pattern import (
    IncidentPatternDetector,
    IncidentPatternReport,
    PatternFrequency,
    PatternOccurrence,
    PatternRecord,
    PatternSeverity,
    PatternType,
)


def _engine(**kw) -> IncidentPatternDetector:
    return IncidentPatternDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_recurring_failure(self):
        assert PatternType.RECURRING_FAILURE == "recurring_failure"

    def test_type_cascading_impact(self):
        assert PatternType.CASCADING_IMPACT == "cascading_impact"

    def test_type_time_based(self):
        assert PatternType.TIME_BASED == "time_based"

    def test_type_deployment_related(self):
        assert PatternType.DEPLOYMENT_RELATED == "deployment_related"

    def test_type_configuration_drift(self):
        assert PatternType.CONFIGURATION_DRIFT == "configuration_drift"

    def test_severity_critical(self):
        assert PatternSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert PatternSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert PatternSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert PatternSeverity.LOW == "low"

    def test_severity_informational(self):
        assert PatternSeverity.INFORMATIONAL == "informational"

    def test_frequency_daily(self):
        assert PatternFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert PatternFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert PatternFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert PatternFrequency.QUARTERLY == "quarterly"

    def test_frequency_rare(self):
        assert PatternFrequency.RARE == "rare"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_pattern_record_defaults(self):
        r = PatternRecord()
        assert r.id
        assert r.pattern_id == ""
        assert r.pattern_type == PatternType.RECURRING_FAILURE
        assert r.pattern_severity == PatternSeverity.INFORMATIONAL
        assert r.pattern_frequency == PatternFrequency.RARE
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_pattern_occurrence_defaults(self):
        m = PatternOccurrence()
        assert m.id
        assert m.pattern_id == ""
        assert m.pattern_type == PatternType.RECURRING_FAILURE
        assert m.occurrence_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_incident_pattern_report_defaults(self):
        r = IncidentPatternReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_occurrences == 0
        assert r.critical_patterns == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_frequency == {}
        assert r.top_patterns == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_pattern
# ---------------------------------------------------------------------------


class TestRecordPattern:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING_FAILURE,
            pattern_severity=PatternSeverity.CRITICAL,
            pattern_frequency=PatternFrequency.DAILY,
            confidence_score=0.95,
            service="api-gateway",
            team="sre",
        )
        assert r.pattern_id == "PAT-001"
        assert r.pattern_type == PatternType.RECURRING_FAILURE
        assert r.pattern_severity == PatternSeverity.CRITICAL
        assert r.pattern_frequency == PatternFrequency.DAILY
        assert r.confidence_score == 0.95
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pattern(pattern_id=f"PAT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_pattern
# ---------------------------------------------------------------------------


class TestGetPattern:
    def test_found(self):
        eng = _engine()
        r = eng.record_pattern(
            pattern_id="PAT-001",
            pattern_severity=PatternSeverity.CRITICAL,
        )
        result = eng.get_pattern(r.id)
        assert result is not None
        assert result.pattern_severity == PatternSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pattern("nonexistent") is None


# ---------------------------------------------------------------------------
# list_patterns
# ---------------------------------------------------------------------------


class TestListPatterns:
    def test_list_all(self):
        eng = _engine()
        eng.record_pattern(pattern_id="PAT-001")
        eng.record_pattern(pattern_id="PAT-002")
        assert len(eng.list_patterns()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING_FAILURE,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_type=PatternType.CASCADING_IMPACT,
        )
        results = eng.list_patterns(
            pattern_type=PatternType.RECURRING_FAILURE,
        )
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_severity=PatternSeverity.CRITICAL,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_severity=PatternSeverity.LOW,
        )
        results = eng.list_patterns(
            severity=PatternSeverity.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_pattern(pattern_id="PAT-001", service="api-gateway")
        eng.record_pattern(pattern_id="PAT-002", service="auth-svc")
        results = eng.list_patterns(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_pattern(pattern_id="PAT-001", team="sre")
        eng.record_pattern(pattern_id="PAT-002", team="platform")
        results = eng.list_patterns(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pattern(pattern_id=f"PAT-{i}")
        assert len(eng.list_patterns(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_occurrence
# ---------------------------------------------------------------------------


class TestAddOccurrence:
    def test_basic(self):
        eng = _engine()
        m = eng.add_occurrence(
            pattern_id="PAT-001",
            pattern_type=PatternType.CASCADING_IMPACT,
            occurrence_score=85.0,
            threshold=90.0,
            breached=True,
            description="Pattern recurrence detected",
        )
        assert m.pattern_id == "PAT-001"
        assert m.pattern_type == PatternType.CASCADING_IMPACT
        assert m.occurrence_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Pattern recurrence detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_occurrence(pattern_id=f"PAT-{i}")
        assert len(eng._occurrences) == 2


# ---------------------------------------------------------------------------
# analyze_pattern_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePatternDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING_FAILURE,
            confidence_score=0.80,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_type=PatternType.RECURRING_FAILURE,
            confidence_score=0.90,
        )
        result = eng.analyze_pattern_distribution()
        assert "recurring_failure" in result
        assert result["recurring_failure"]["count"] == 2
        assert result["recurring_failure"]["avg_confidence"] == 0.85

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_pattern_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_patterns
# ---------------------------------------------------------------------------


class TestIdentifyCriticalPatterns:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_severity=PatternSeverity.CRITICAL,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_severity=PatternSeverity.LOW,
        )
        results = eng.identify_critical_patterns()
        assert len(results) == 1
        assert results[0]["pattern_id"] == "PAT-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_patterns() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_ranked(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            service="api-gateway",
            confidence_score=0.95,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            service="api-gateway",
            confidence_score=0.85,
        )
        eng.record_pattern(
            pattern_id="PAT-003",
            service="auth-svc",
            confidence_score=0.70,
        )
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_confidence"] == 0.9

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_pattern_trends
# ---------------------------------------------------------------------------


class TestDetectPatternTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_occurrence(pattern_id="PAT-1", occurrence_score=val)
        result = eng.detect_pattern_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_occurrence(pattern_id="PAT-1", occurrence_score=val)
        result = eng.detect_pattern_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_pattern_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING_FAILURE,
            pattern_severity=PatternSeverity.CRITICAL,
            pattern_frequency=PatternFrequency.DAILY,
            confidence_score=0.95,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentPatternReport)
        assert report.total_records == 1
        assert report.critical_patterns == 1
        assert len(report.top_patterns) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_pattern(pattern_id="PAT-001")
        eng.add_occurrence(pattern_id="PAT-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._occurrences) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_occurrences"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING_FAILURE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "recurring_failure" in stats["type_distribution"]

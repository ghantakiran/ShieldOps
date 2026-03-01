"""Tests for shieldops.incidents.incident_pattern_analyzer — IncidentPatternAnalyzer."""

from __future__ import annotations

from shieldops.incidents.incident_pattern_analyzer import (
    IncidentPatternAnalyzer,
    IncidentPatternReport,
    PatternAnalysis,
    PatternConfidence,
    PatternRecord,
    PatternScope,
    PatternType,
)


def _engine(**kw) -> IncidentPatternAnalyzer:
    return IncidentPatternAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_recurring(self):
        assert PatternType.RECURRING == "recurring"

    def test_type_seasonal(self):
        assert PatternType.SEASONAL == "seasonal"

    def test_type_cascading(self):
        assert PatternType.CASCADING == "cascading"

    def test_type_correlated(self):
        assert PatternType.CORRELATED == "correlated"

    def test_type_isolated(self):
        assert PatternType.ISOLATED == "isolated"

    def test_confidence_very_high(self):
        assert PatternConfidence.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert PatternConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert PatternConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert PatternConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert PatternConfidence.SPECULATIVE == "speculative"

    def test_scope_single_service(self):
        assert PatternScope.SINGLE_SERVICE == "single_service"

    def test_scope_multi_service(self):
        assert PatternScope.MULTI_SERVICE == "multi_service"

    def test_scope_platform_wide(self):
        assert PatternScope.PLATFORM_WIDE == "platform_wide"

    def test_scope_infrastructure(self):
        assert PatternScope.INFRASTRUCTURE == "infrastructure"

    def test_scope_external(self):
        assert PatternScope.EXTERNAL == "external"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_pattern_record_defaults(self):
        r = PatternRecord()
        assert r.id
        assert r.pattern_id == ""
        assert r.pattern_type == PatternType.ISOLATED
        assert r.pattern_confidence == PatternConfidence.SPECULATIVE
        assert r.pattern_scope == PatternScope.SINGLE_SERVICE
        assert r.frequency_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_pattern_analysis_defaults(self):
        a = PatternAnalysis()
        assert a.id
        assert a.pattern_id == ""
        assert a.pattern_type == PatternType.ISOLATED
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_incident_pattern_report_defaults(self):
        r = IncidentPatternReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.recurring_patterns == 0
        assert r.avg_frequency_score == 0.0
        assert r.by_type == {}
        assert r.by_confidence == {}
        assert r.by_scope == {}
        assert r.top_recurring == []
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
            pattern_type=PatternType.RECURRING,
            pattern_confidence=PatternConfidence.HIGH,
            pattern_scope=PatternScope.MULTI_SERVICE,
            frequency_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.pattern_id == "PAT-001"
        assert r.pattern_type == PatternType.RECURRING
        assert r.pattern_confidence == PatternConfidence.HIGH
        assert r.pattern_scope == PatternScope.MULTI_SERVICE
        assert r.frequency_score == 85.0
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
            pattern_type=PatternType.RECURRING,
        )
        result = eng.get_pattern(r.id)
        assert result is not None
        assert result.pattern_type == PatternType.RECURRING

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
            pattern_type=PatternType.RECURRING,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_type=PatternType.SEASONAL,
        )
        results = eng.list_patterns(pattern_type=PatternType.RECURRING)
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_confidence=PatternConfidence.HIGH,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_confidence=PatternConfidence.LOW,
        )
        results = eng.list_patterns(
            pattern_confidence=PatternConfidence.HIGH,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_pattern(pattern_id="PAT-001", service="api-gateway")
        eng.record_pattern(pattern_id="PAT-002", service="auth")
        results = eng.list_patterns(service="api-gateway")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pattern(pattern_id=f"PAT-{i}")
        assert len(eng.list_patterns(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING,
            analysis_score=78.0,
            threshold=70.0,
            breached=True,
            description="High frequency recurring pattern",
        )
        assert a.pattern_id == "PAT-001"
        assert a.pattern_type == PatternType.RECURRING
        assert a.analysis_score == 78.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(pattern_id=f"PAT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_pattern_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePatternDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING,
            frequency_score=80.0,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_type=PatternType.RECURRING,
            frequency_score=60.0,
        )
        result = eng.analyze_pattern_distribution()
        assert "recurring" in result
        assert result["recurring"]["count"] == 2
        assert result["recurring"]["avg_frequency_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_pattern_distribution() == {}


# ---------------------------------------------------------------------------
# identify_recurring_patterns
# ---------------------------------------------------------------------------


class TestIdentifyRecurringPatterns:
    def test_detects_recurring(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            pattern_type=PatternType.ISOLATED,
        )
        results = eng.identify_recurring_patterns()
        assert len(results) == 1
        assert results[0]["pattern_id"] == "PAT-001"

    def test_detects_cascading(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.CASCADING,
        )
        results = eng.identify_recurring_patterns()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_recurring_patterns() == []


# ---------------------------------------------------------------------------
# rank_by_frequency
# ---------------------------------------------------------------------------


class TestRankByFrequency:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            service="api-gateway",
            frequency_score=90.0,
        )
        eng.record_pattern(
            pattern_id="PAT-002",
            service="auth",
            frequency_score=40.0,
        )
        results = eng.rank_by_frequency()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_frequency_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_frequency() == []


# ---------------------------------------------------------------------------
# detect_pattern_trends
# ---------------------------------------------------------------------------


class TestDetectPatternTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(pattern_id="PAT-001", analysis_score=50.0)
        result = eng.detect_pattern_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        eng.add_analysis(pattern_id="PAT-001", analysis_score=10.0)
        eng.add_analysis(pattern_id="PAT-002", analysis_score=10.0)
        eng.add_analysis(pattern_id="PAT-003", analysis_score=80.0)
        eng.add_analysis(pattern_id="PAT-004", analysis_score=80.0)
        result = eng.detect_pattern_trends()
        assert result["trend"] == "growing"
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
            pattern_type=PatternType.RECURRING,
            pattern_confidence=PatternConfidence.HIGH,
            frequency_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentPatternReport)
        assert report.total_records == 1
        assert report.recurring_patterns == 1
        assert len(report.top_recurring) == 1
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
        eng.add_analysis(pattern_id="PAT-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["pattern_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_pattern(
            pattern_id="PAT-001",
            pattern_type=PatternType.RECURRING,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "recurring" in stats["pattern_type_distribution"]

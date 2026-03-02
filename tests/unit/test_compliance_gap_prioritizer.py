"""Tests for shieldops.compliance.compliance_gap_prioritizer — ComplianceGapPrioritizer."""

from __future__ import annotations

from shieldops.compliance.compliance_gap_prioritizer import (
    ComplianceGapPrioritizer,
    GapAnalysis,
    GapCategory,
    GapPrioritizationReport,
    GapRecord,
    PriorityLevel,
    RemediationEffort,
)


def _engine(**kw) -> ComplianceGapPrioritizer:
    return ComplianceGapPrioritizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_gapcategory_policy(self):
        assert GapCategory.POLICY == "policy"

    def test_gapcategory_technical(self):
        assert GapCategory.TECHNICAL == "technical"

    def test_gapcategory_process(self):
        assert GapCategory.PROCESS == "process"

    def test_gapcategory_people(self):
        assert GapCategory.PEOPLE == "people"

    def test_gapcategory_documentation(self):
        assert GapCategory.DOCUMENTATION == "documentation"

    def test_prioritylevel_critical(self):
        assert PriorityLevel.CRITICAL == "critical"

    def test_prioritylevel_high(self):
        assert PriorityLevel.HIGH == "high"

    def test_prioritylevel_medium(self):
        assert PriorityLevel.MEDIUM == "medium"

    def test_prioritylevel_low(self):
        assert PriorityLevel.LOW == "low"

    def test_prioritylevel_informational(self):
        assert PriorityLevel.INFORMATIONAL == "informational"

    def test_remediationeffort_minimal(self):
        assert RemediationEffort.MINIMAL == "minimal"

    def test_remediationeffort_low(self):
        assert RemediationEffort.LOW == "low"

    def test_remediationeffort_moderate(self):
        assert RemediationEffort.MODERATE == "moderate"

    def test_remediationeffort_high(self):
        assert RemediationEffort.HIGH == "high"

    def test_remediationeffort_extensive(self):
        assert RemediationEffort.EXTENSIVE == "extensive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_gaprecord_defaults(self):
        r = GapRecord()
        assert r.id
        assert r.gap_name == ""
        assert r.gap_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_gapanalysis_defaults(self):
        c = GapAnalysis()
        assert c.id
        assert c.gap_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_gapprioritizationreport_defaults(self):
        r = GapPrioritizationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_priority_count == 0
        assert r.avg_gap_score == 0
        assert r.by_category == {}
        assert r.by_priority == {}
        assert r.by_effort == {}
        assert r.top_high_priority == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_gap
# ---------------------------------------------------------------------------


class TestRecordGap:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gap(
            gap_name="test-item",
            gap_category=GapCategory.TECHNICAL,
            gap_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.gap_name == "test-item"
        assert r.gap_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(gap_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_gap
# ---------------------------------------------------------------------------


class TestGetGap:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap(gap_name="test-item")
        result = eng.get_gap(r.id)
        assert result is not None
        assert result.gap_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None


# ---------------------------------------------------------------------------
# list_gaps
# ---------------------------------------------------------------------------


class TestListGaps:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap(gap_name="ITEM-001")
        eng.record_gap(gap_name="ITEM-002")
        assert len(eng.list_gaps()) == 2

    def test_filter_by_gap_category(self):
        eng = _engine()
        eng.record_gap(gap_name="ITEM-001", gap_category=GapCategory.POLICY)
        eng.record_gap(gap_name="ITEM-002", gap_category=GapCategory.TECHNICAL)
        results = eng.list_gaps(gap_category=GapCategory.POLICY)
        assert len(results) == 1

    def test_filter_by_priority_level(self):
        eng = _engine()
        eng.record_gap(gap_name="ITEM-001", priority_level=PriorityLevel.CRITICAL)
        eng.record_gap(gap_name="ITEM-002", priority_level=PriorityLevel.HIGH)
        results = eng.list_gaps(priority_level=PriorityLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_gap(gap_name="ITEM-001", team="security")
        eng.record_gap(gap_name="ITEM-002", team="platform")
        results = eng.list_gaps(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gap(gap_name=f"ITEM-{i}")
        assert len(eng.list_gaps(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            gap_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.gap_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(gap_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_category_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap(gap_name="ITEM-001", gap_category=GapCategory.POLICY, gap_score=90.0)
        eng.record_gap(gap_name="ITEM-002", gap_category=GapCategory.POLICY, gap_score=70.0)
        result = eng.analyze_category_distribution()
        assert "policy" in result
        assert result["policy"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_priority_gaps
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(gap_priority_threshold=60.0)
        eng.record_gap(gap_name="ITEM-001", gap_score=90.0)
        eng.record_gap(gap_name="ITEM-002", gap_score=40.0)
        results = eng.identify_high_priority_gaps()
        assert len(results) == 1
        assert results[0]["gap_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(gap_priority_threshold=60.0)
        eng.record_gap(gap_name="ITEM-001", gap_score=80.0)
        eng.record_gap(gap_name="ITEM-002", gap_score=95.0)
        results = eng.identify_high_priority_gaps()
        assert len(results) == 2
        assert results[0]["gap_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_priority_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_gap_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_gap(gap_name="ITEM-001", service="auth-svc", gap_score=90.0)
        eng.record_gap(gap_name="ITEM-002", service="api-gw", gap_score=50.0)
        results = eng.rank_by_gap_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_gap_score() == []


# ---------------------------------------------------------------------------
# detect_gap_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(gap_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_gap_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(gap_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(gap_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(gap_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(gap_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_gap_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_gap_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(gap_priority_threshold=60.0)
        eng.record_gap(gap_name="test-item", gap_score=90.0)
        report = eng.generate_report()
        assert isinstance(report, GapPrioritizationReport)
        assert report.total_records == 1
        assert report.high_priority_count == 1
        assert len(report.top_high_priority) == 1
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
        eng.record_gap(gap_name="ITEM-001")
        eng.add_analysis(gap_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_gap(
            gap_name="ITEM-001",
            gap_category=GapCategory.POLICY,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

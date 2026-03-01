"""Tests for shieldops.knowledge.knowledge_gap_detector — KnowledgeGapDetector."""

from __future__ import annotations

from shieldops.knowledge.knowledge_gap_detector import (
    GapAssessment,
    GapDomain,
    GapSeverity,
    GapStatus,
    KnowledgeGapDetector,
    KnowledgeGapRecord,
    KnowledgeGapReport,
)


def _engine(**kw) -> KnowledgeGapDetector:
    return KnowledgeGapDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert GapSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert GapSeverity.LOW == "low"

    def test_severity_informational(self):
        assert GapSeverity.INFORMATIONAL == "informational"

    def test_domain_infrastructure(self):
        assert GapDomain.INFRASTRUCTURE == "infrastructure"

    def test_domain_application(self):
        assert GapDomain.APPLICATION == "application"

    def test_domain_security(self):
        assert GapDomain.SECURITY == "security"

    def test_domain_networking(self):
        assert GapDomain.NETWORKING == "networking"

    def test_domain_database(self):
        assert GapDomain.DATABASE == "database"

    def test_status_open(self):
        assert GapStatus.OPEN == "open"

    def test_status_in_progress(self):
        assert GapStatus.IN_PROGRESS == "in_progress"

    def test_status_documented(self):
        assert GapStatus.DOCUMENTED == "documented"

    def test_status_verified(self):
        assert GapStatus.VERIFIED == "verified"

    def test_status_closed(self):
        assert GapStatus.CLOSED == "closed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_gap_record_defaults(self):
        r = KnowledgeGapRecord()
        assert r.id
        assert r.gap_id == ""
        assert r.gap_severity == GapSeverity.MODERATE
        assert r.gap_domain == GapDomain.INFRASTRUCTURE
        assert r.gap_status == GapStatus.OPEN
        assert r.coverage_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_gap_assessment_defaults(self):
        a = GapAssessment()
        assert a.id
        assert a.gap_id == ""
        assert a.gap_severity == GapSeverity.MODERATE
        assert a.assessment_score == 0.0
        assert a.threshold == 80.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_gap_report_defaults(self):
        r = KnowledgeGapReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.critical_gaps == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_severity == {}
        assert r.by_domain == {}
        assert r.by_status == {}
        assert r.top_gap_areas == []
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
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
            gap_domain=GapDomain.SECURITY,
            gap_status=GapStatus.OPEN,
            coverage_pct=40.0,
            service="auth-svc",
            team="sre",
        )
        assert r.gap_id == "GAP-001"
        assert r.gap_severity == GapSeverity.CRITICAL
        assert r.gap_domain == GapDomain.SECURITY
        assert r.gap_status == GapStatus.OPEN
        assert r.coverage_pct == 40.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(gap_id=f"GAP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_gap
# ---------------------------------------------------------------------------


class TestGetGap:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.HIGH,
        )
        result = eng.get_gap(r.id)
        assert result is not None
        assert result.gap_severity == GapSeverity.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None


# ---------------------------------------------------------------------------
# list_gaps
# ---------------------------------------------------------------------------


class TestListGaps:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001")
        eng.record_gap(gap_id="GAP-002")
        assert len(eng.list_gaps()) == 2

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", gap_severity=GapSeverity.CRITICAL)
        eng.record_gap(gap_id="GAP-002", gap_severity=GapSeverity.LOW)
        results = eng.list_gaps(gap_severity=GapSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", gap_domain=GapDomain.SECURITY)
        eng.record_gap(gap_id="GAP-002", gap_domain=GapDomain.DATABASE)
        results = eng.list_gaps(gap_domain=GapDomain.SECURITY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", team="sre")
        eng.record_gap(gap_id="GAP-002", team="platform")
        results = eng.list_gaps(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gap(gap_id=f"GAP-{i}")
        assert len(eng.list_gaps(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            gap_id="GAP-001",
            gap_severity=GapSeverity.HIGH,
            assessment_score=60.0,
            threshold=80.0,
            description="Below coverage",
        )
        assert a.gap_id == "GAP-001"
        assert a.gap_severity == GapSeverity.HIGH
        assert a.assessment_score == 60.0
        assert a.breached is True

    def test_not_breached(self):
        eng = _engine()
        a = eng.add_assessment(
            gap_id="GAP-002",
            assessment_score=90.0,
            threshold=80.0,
        )
        assert a.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(gap_id=f"GAP-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_gap_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeGapDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
            coverage_pct=30.0,
        )
        eng.record_gap(
            gap_id="GAP-002",
            gap_severity=GapSeverity.CRITICAL,
            coverage_pct=50.0,
        )
        result = eng.analyze_gap_distribution()
        assert "critical" in result
        assert result["critical"]["count"] == 2
        assert result["critical"]["avg_coverage_pct"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_gap_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCriticalGaps:
    def test_detects_critical_and_high(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", gap_severity=GapSeverity.CRITICAL)
        eng.record_gap(gap_id="GAP-002", gap_severity=GapSeverity.HIGH)
        eng.record_gap(gap_id="GAP-003", gap_severity=GapSeverity.LOW)
        results = eng.identify_critical_gaps()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage
# ---------------------------------------------------------------------------


class TestRankByCoverage:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_gap(gap_id="GAP-001", service="api", coverage_pct=90.0)
        eng.record_gap(gap_id="GAP-002", service="db", coverage_pct=30.0)
        results = eng.rank_by_coverage()
        assert len(results) == 2
        assert results[0]["service"] == "db"
        assert results[0]["avg_coverage_pct"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage() == []


# ---------------------------------------------------------------------------
# detect_gap_trends
# ---------------------------------------------------------------------------


class TestDetectGapTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(gap_id="GAP-001", assessment_score=50.0)
        result = eng.detect_gap_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(gap_id="GAP-001", assessment_score=30.0)
        eng.add_assessment(gap_id="GAP-002", assessment_score=30.0)
        eng.add_assessment(gap_id="GAP-003", assessment_score=80.0)
        eng.add_assessment(gap_id="GAP-004", assessment_score=80.0)
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
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
            gap_domain=GapDomain.SECURITY,
            coverage_pct=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeGapReport)
        assert report.total_records == 1
        assert report.critical_gaps == 1
        assert len(report.top_gap_areas) == 1
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
        eng.record_gap(gap_id="GAP-001")
        eng.add_assessment(gap_id="GAP-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_gap(
            gap_id="GAP-001",
            gap_severity=GapSeverity.CRITICAL,
            team="sre",
            service="api",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "critical" in stats["severity_distribution"]

"""Tests for shieldops.sla.slo_breach_analyzer — SLOBreachAnalyzer."""

from __future__ import annotations

from shieldops.sla.slo_breach_analyzer import (
    BreachCause,
    BreachImpactAssessment,
    BreachRecord,
    BreachSeverity,
    BreachType,
    SLOBreachAnalyzer,
    SLOBreachReport,
)


def _engine(**kw) -> SLOBreachAnalyzer:
    return SLOBreachAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_availability(self):
        assert BreachType.AVAILABILITY == "availability"

    def test_type_latency(self):
        assert BreachType.LATENCY == "latency"

    def test_type_error_rate(self):
        assert BreachType.ERROR_RATE == "error_rate"

    def test_type_throughput(self):
        assert BreachType.THROUGHPUT == "throughput"

    def test_type_durability(self):
        assert BreachType.DURABILITY == "durability"

    def test_severity_critical(self):
        assert BreachSeverity.CRITICAL == "critical"

    def test_severity_major(self):
        assert BreachSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert BreachSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert BreachSeverity.MINOR == "minor"

    def test_severity_cosmetic(self):
        assert BreachSeverity.COSMETIC == "cosmetic"

    def test_cause_infrastructure_failure(self):
        assert BreachCause.INFRASTRUCTURE_FAILURE == "infrastructure_failure"

    def test_cause_code_bug(self):
        assert BreachCause.CODE_BUG == "code_bug"

    def test_cause_dependency_issue(self):
        assert BreachCause.DEPENDENCY_ISSUE == "dependency_issue"

    def test_cause_capacity_limit(self):
        assert BreachCause.CAPACITY_LIMIT == "capacity_limit"

    def test_cause_external_factor(self):
        assert BreachCause.EXTERNAL_FACTOR == "external_factor"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_breach_record_defaults(self):
        r = BreachRecord()
        assert r.id
        assert r.breach_id == ""
        assert r.breach_type == BreachType.AVAILABILITY
        assert r.breach_severity == BreachSeverity.MODERATE
        assert r.breach_cause == BreachCause.INFRASTRUCTURE_FAILURE
        assert r.breach_duration_minutes == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_breach_impact_assessment_defaults(self):
        a = BreachImpactAssessment()
        assert a.id
        assert a.breach_id == ""
        assert a.breach_type == BreachType.AVAILABILITY
        assert a.impact_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_slo_breach_report_defaults(self):
        r = SLOBreachReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.critical_breaches == 0
        assert r.avg_breach_duration_minutes == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_cause == {}
        assert r.top_breaching_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_breach
# ---------------------------------------------------------------------------


class TestRecordBreach:
    def test_basic(self):
        eng = _engine()
        r = eng.record_breach(
            breach_id="BRE-001",
            breach_type=BreachType.LATENCY,
            breach_severity=BreachSeverity.CRITICAL,
            breach_cause=BreachCause.CODE_BUG,
            breach_duration_minutes=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.breach_id == "BRE-001"
        assert r.breach_type == BreachType.LATENCY
        assert r.breach_severity == BreachSeverity.CRITICAL
        assert r.breach_cause == BreachCause.CODE_BUG
        assert r.breach_duration_minutes == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_breach(breach_id=f"BRE-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_breach
# ---------------------------------------------------------------------------


class TestGetBreach:
    def test_found(self):
        eng = _engine()
        r = eng.record_breach(
            breach_id="BRE-001",
            breach_severity=BreachSeverity.CRITICAL,
        )
        result = eng.get_breach(r.id)
        assert result is not None
        assert result.breach_severity == BreachSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_breach("nonexistent") is None


# ---------------------------------------------------------------------------
# list_breaches
# ---------------------------------------------------------------------------


class TestListBreaches:
    def test_list_all(self):
        eng = _engine()
        eng.record_breach(breach_id="BRE-001")
        eng.record_breach(breach_id="BRE-002")
        assert len(eng.list_breaches()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_type=BreachType.AVAILABILITY,
        )
        eng.record_breach(
            breach_id="BRE-002",
            breach_type=BreachType.LATENCY,
        )
        results = eng.list_breaches(
            breach_type=BreachType.AVAILABILITY,
        )
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_severity=BreachSeverity.CRITICAL,
        )
        eng.record_breach(
            breach_id="BRE-002",
            breach_severity=BreachSeverity.MINOR,
        )
        results = eng.list_breaches(
            breach_severity=BreachSeverity.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_breach(breach_id="BRE-001", team="sre")
        eng.record_breach(breach_id="BRE-002", team="platform")
        results = eng.list_breaches(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_breach(breach_id=f"BRE-{i}")
        assert len(eng.list_breaches(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            breach_id="BRE-001",
            breach_type=BreachType.LATENCY,
            impact_score=85.0,
            threshold=70.0,
            breached=True,
            description="High latency impact",
        )
        assert a.breach_id == "BRE-001"
        assert a.breach_type == BreachType.LATENCY
        assert a.impact_score == 85.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(breach_id=f"BRE-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_breach_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeBreachDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_type=BreachType.AVAILABILITY,
            breach_duration_minutes=10.0,
        )
        eng.record_breach(
            breach_id="BRE-002",
            breach_type=BreachType.AVAILABILITY,
            breach_duration_minutes=20.0,
        )
        result = eng.analyze_breach_distribution()
        assert "availability" in result
        assert result["availability"]["count"] == 2
        assert result["availability"]["avg_duration"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_breach_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_breaches
# ---------------------------------------------------------------------------


class TestIdentifyCriticalBreaches:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_severity=BreachSeverity.CRITICAL,
        )
        eng.record_breach(
            breach_id="BRE-002",
            breach_severity=BreachSeverity.MINOR,
        )
        results = eng.identify_critical_breaches()
        assert len(results) == 1
        assert results[0]["breach_id"] == "BRE-001"

    def test_detects_major(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_severity=BreachSeverity.MAJOR,
        )
        results = eng.identify_critical_breaches()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_breaches() == []


# ---------------------------------------------------------------------------
# rank_by_breach_duration
# ---------------------------------------------------------------------------


class TestRankByBreachDuration:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            service="api-gateway",
            breach_duration_minutes=30.0,
        )
        eng.record_breach(
            breach_id="BRE-002",
            service="pay-svc",
            breach_duration_minutes=10.0,
        )
        results = eng.rank_by_breach_duration()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_duration"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_breach_duration() == []


# ---------------------------------------------------------------------------
# detect_breach_trends
# ---------------------------------------------------------------------------


class TestDetectBreachTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(breach_id="BRE-001", impact_score=50.0)
        result = eng.detect_breach_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(breach_id="BRE-001", impact_score=30.0)
        eng.add_assessment(breach_id="BRE-002", impact_score=30.0)
        eng.add_assessment(breach_id="BRE-003", impact_score=80.0)
        eng.add_assessment(breach_id="BRE-004", impact_score=80.0)
        result = eng.detect_breach_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_breach_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_type=BreachType.LATENCY,
            breach_severity=BreachSeverity.CRITICAL,
            breach_cause=BreachCause.CODE_BUG,
            breach_duration_minutes=90.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SLOBreachReport)
        assert report.total_records == 1
        assert report.critical_breaches == 1
        assert len(report.top_breaching_services) == 1
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
        eng.record_breach(breach_id="BRE-001")
        eng.add_assessment(breach_id="BRE-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_breach(
            breach_id="BRE-001",
            breach_type=BreachType.AVAILABILITY,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "availability" in stats["type_distribution"]

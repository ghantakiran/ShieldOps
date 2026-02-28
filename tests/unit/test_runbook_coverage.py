"""Tests for shieldops.operations.runbook_coverage — RunbookCoverageAnalyzer."""

from __future__ import annotations

from shieldops.operations.runbook_coverage import (
    CoverageGap,
    CoverageGapDetail,
    CoverageLevel,
    CoverageRecord,
    IncidentType,
    RunbookCoverageAnalyzer,
    RunbookCoverageReport,
)


def _engine(**kw) -> RunbookCoverageAnalyzer:
    return RunbookCoverageAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CoverageLevel (5)
    def test_level_full(self):
        assert CoverageLevel.FULL == "full"

    def test_level_high(self):
        assert CoverageLevel.HIGH == "high"

    def test_level_partial(self):
        assert CoverageLevel.PARTIAL == "partial"

    def test_level_minimal(self):
        assert CoverageLevel.MINIMAL == "minimal"

    def test_level_none(self):
        assert CoverageLevel.NONE == "none"

    # IncidentType (5)
    def test_type_outage(self):
        assert IncidentType.OUTAGE == "outage"

    def test_type_degradation(self):
        assert IncidentType.DEGRADATION == "degradation"

    def test_type_security_breach(self):
        assert IncidentType.SECURITY_BREACH == "security_breach"

    def test_type_data_loss(self):
        assert IncidentType.DATA_LOSS == "data_loss"

    def test_type_capacity(self):
        assert IncidentType.CAPACITY == "capacity"

    # CoverageGap (5)
    def test_gap_missing_runbook(self):
        assert CoverageGap.MISSING_RUNBOOK == "missing_runbook"

    def test_gap_outdated_runbook(self):
        assert CoverageGap.OUTDATED_RUNBOOK == "outdated_runbook"

    def test_gap_incomplete_steps(self):
        assert CoverageGap.INCOMPLETE_STEPS == "incomplete_steps"

    def test_gap_no_automation(self):
        assert CoverageGap.NO_AUTOMATION == "no_automation"

    def test_gap_untested(self):
        assert CoverageGap.UNTESTED == "untested"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_coverage_record_defaults(self):
        r = CoverageRecord()
        assert r.id
        assert r.service == ""
        assert r.incident_type == IncidentType.OUTAGE
        assert r.coverage_level == CoverageLevel.NONE
        assert r.coverage_score == 0.0
        assert r.gap is None
        assert r.runbook_count == 0
        assert r.automated is False
        assert r.created_at > 0

    def test_coverage_gap_detail_defaults(self):
        r = CoverageGapDetail()
        assert r.id
        assert r.service == ""
        assert r.incident_type == IncidentType.OUTAGE
        assert r.gap == CoverageGap.MISSING_RUNBOOK
        assert r.priority == ""
        assert r.recommended_action == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = RunbookCoverageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_gaps == 0
        assert r.fully_covered == 0
        assert r.uncovered == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_coverage_level == {}
        assert r.by_incident_type == {}
        assert r.by_gap_type == {}
        assert r.top_uncovered_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_coverage
# -------------------------------------------------------------------


class TestRecordCoverage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coverage("api-gateway")
        assert r.service == "api-gateway"
        assert r.coverage_level == CoverageLevel.NONE

    def test_with_params(self):
        eng = _engine()
        r = eng.record_coverage(
            "payment-service",
            incident_type=IncidentType.DATA_LOSS,
            coverage_level=CoverageLevel.FULL,
            coverage_score=0.95,
            gap=CoverageGap.UNTESTED,
            runbook_count=5,
            automated=True,
        )
        assert r.coverage_level == CoverageLevel.FULL
        assert r.incident_type == IncidentType.DATA_LOSS
        assert r.automated is True
        assert r.runbook_count == 5

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_coverage("svc-a")
        r2 = eng.record_coverage("svc-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coverage(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_coverage
# -------------------------------------------------------------------


class TestGetCoverage:
    def test_found(self):
        eng = _engine()
        r = eng.record_coverage("svc-x")
        assert eng.get_coverage(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_coverage("nonexistent") is None


# -------------------------------------------------------------------
# list_coverages
# -------------------------------------------------------------------


class TestListCoverages:
    def test_list_all(self):
        eng = _engine()
        eng.record_coverage("svc-a")
        eng.record_coverage("svc-b")
        assert len(eng.list_coverages()) == 2

    def test_filter_by_coverage_level(self):
        eng = _engine()
        eng.record_coverage("svc-a", coverage_level=CoverageLevel.FULL)
        eng.record_coverage("svc-b", coverage_level=CoverageLevel.NONE)
        results = eng.list_coverages(coverage_level=CoverageLevel.FULL)
        assert len(results) == 1
        assert results[0].coverage_level == CoverageLevel.FULL

    def test_filter_by_incident_type(self):
        eng = _engine()
        eng.record_coverage("svc-a", incident_type=IncidentType.OUTAGE)
        eng.record_coverage("svc-b", incident_type=IncidentType.CAPACITY)
        results = eng.list_coverages(incident_type=IncidentType.OUTAGE)
        assert len(results) == 1

    def test_filter_by_gap(self):
        eng = _engine()
        eng.record_coverage("svc-a", gap=CoverageGap.MISSING_RUNBOOK)
        eng.record_coverage("svc-b", gap=CoverageGap.UNTESTED)
        results = eng.list_coverages(gap=CoverageGap.MISSING_RUNBOOK)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_coverage(f"svc-{i}")
        assert len(eng.list_coverages(limit=5)) == 5


# -------------------------------------------------------------------
# add_gap
# -------------------------------------------------------------------


class TestAddGap:
    def test_basic(self):
        eng = _engine()
        g = eng.add_gap("auth-service")
        assert g.service == "auth-service"
        assert g.gap == CoverageGap.MISSING_RUNBOOK

    def test_with_params(self):
        eng = _engine()
        g = eng.add_gap(
            "db-service",
            incident_type=IncidentType.DATA_LOSS,
            gap=CoverageGap.NO_AUTOMATION,
            priority="high",
            recommended_action="Automate failover runbook",
        )
        assert g.incident_type == IncidentType.DATA_LOSS
        assert g.gap == CoverageGap.NO_AUTOMATION
        assert g.priority == "high"

    def test_unique_gap_ids(self):
        eng = _engine()
        g1 = eng.add_gap("svc-a")
        g2 = eng.add_gap("svc-b")
        assert g1.id != g2.id


# -------------------------------------------------------------------
# analyze_coverage_by_service
# -------------------------------------------------------------------


class TestAnalyzeCoverageByService:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_coverage_by_service()
        assert result["total_services"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        for _ in range(3):
            eng.record_coverage("svc-a", coverage_score=0.8, coverage_level=CoverageLevel.HIGH)
        eng.record_coverage("svc-b", coverage_score=0.2, coverage_level=CoverageLevel.NONE)
        result = eng.analyze_coverage_by_service()
        assert result["total_services"] == 2
        services = [b["service"] for b in result["breakdown"]]
        assert "svc-a" in services

    def test_sorted_by_score_descending(self):
        eng = _engine()
        eng.record_coverage("low-cov", coverage_score=0.1)
        eng.record_coverage("high-cov", coverage_score=0.9)
        result = eng.analyze_coverage_by_service()
        first_score = result["breakdown"][0]["avg_coverage_score"]
        last_score = result["breakdown"][-1]["avg_coverage_score"]
        assert first_score >= last_score


# -------------------------------------------------------------------
# identify_uncovered_scenarios
# -------------------------------------------------------------------


class TestIdentifyUncoveredScenarios:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_uncovered_scenarios() == []

    def test_only_none_returned(self):
        eng = _engine()
        eng.record_coverage("svc-a", coverage_level=CoverageLevel.FULL)
        eng.record_coverage("svc-b", coverage_level=CoverageLevel.NONE)
        results = eng.identify_uncovered_scenarios()
        assert len(results) == 1
        assert results[0]["service"] == "svc-b"

    def test_multiple_uncovered(self):
        eng = _engine()
        for i in range(3):
            eng.record_coverage(f"svc-{i}", coverage_level=CoverageLevel.NONE)
        eng.record_coverage("covered-svc", coverage_level=CoverageLevel.PARTIAL)
        results = eng.identify_uncovered_scenarios()
        assert len(results) == 3


# -------------------------------------------------------------------
# rank_by_coverage_score
# -------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []

    def test_ascending_order(self):
        eng = _engine()
        eng.record_coverage("high-cov", coverage_score=0.9)
        eng.record_coverage("low-cov", coverage_score=0.1)
        results = eng.rank_by_coverage_score()
        assert results[0]["service"] == "low-cov"
        assert results[0]["avg_coverage_score"] <= results[-1]["avg_coverage_score"]


# -------------------------------------------------------------------
# detect_coverage_trends
# -------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_coverage("svc")
        result = eng.detect_coverage_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_coverage("svc", coverage_score=0.5)
        result = eng.detect_coverage_trends()
        assert result["trend"] in ("stable", "improving", "worsening")

    def test_improving_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_coverage("svc", coverage_score=20.0)
        for _ in range(8):
            eng.record_coverage("svc", coverage_score=90.0)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "improving"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, RunbookCoverageReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.add_gap("svc-a", gap=CoverageGap.MISSING_RUNBOOK)
        eng.record_coverage("svc-a", coverage_level=CoverageLevel.NONE, coverage_score=0.0)
        eng.record_coverage("svc-b", coverage_level=CoverageLevel.FULL, coverage_score=1.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_gaps == 1
        assert report.fully_covered == 1
        assert report.uncovered == 1
        assert report.by_coverage_level


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_gaps(self):
        eng = _engine()
        eng.record_coverage("svc-a")
        eng.add_gap("svc-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["automated_count"] == 0

    def test_populated(self):
        eng = _engine(min_coverage_pct=85.0)
        eng.record_coverage(
            "svc-a",
            coverage_level=CoverageLevel.FULL,
            coverage_score=0.95,
            automated=True,
        )
        eng.record_coverage("svc-b", coverage_level=CoverageLevel.NONE, coverage_score=0.0)
        eng.add_gap("svc-b")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_gaps"] == 1
        assert stats["automated_count"] == 1
        assert stats["min_coverage_pct"] == 85.0
        assert stats["unique_services"] == 2
        assert stats["avg_coverage_score"] > 0.0

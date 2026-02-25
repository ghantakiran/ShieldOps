"""Tests for shieldops.observability.coverage_scorer — ObservabilityCoverageScorer."""

from __future__ import annotations

from shieldops.observability.coverage_scorer import (
    CoverageGap,
    GapPriority,
    MaturityLevel,
    ObservabilityCoverageReport,
    ObservabilityCoverageScorer,
    ObservabilityPillar,
    ServiceCoverageRecord,
)


def _engine(**kw) -> ObservabilityCoverageScorer:
    return ObservabilityCoverageScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ObservabilityPillar (5)
    def test_pillar_logging(self):
        assert ObservabilityPillar.LOGGING == "logging"

    def test_pillar_metrics(self):
        assert ObservabilityPillar.METRICS == "metrics"

    def test_pillar_tracing(self):
        assert ObservabilityPillar.TRACING == "tracing"

    def test_pillar_alerting(self):
        assert ObservabilityPillar.ALERTING == "alerting"

    def test_pillar_dashboards(self):
        assert ObservabilityPillar.DASHBOARDS == "dashboards"

    # MaturityLevel (5)
    def test_maturity_none(self):
        assert MaturityLevel.NONE == "none"

    def test_maturity_basic(self):
        assert MaturityLevel.BASIC == "basic"

    def test_maturity_intermediate(self):
        assert MaturityLevel.INTERMEDIATE == "intermediate"

    def test_maturity_advanced(self):
        assert MaturityLevel.ADVANCED == "advanced"

    def test_maturity_exemplary(self):
        assert MaturityLevel.EXEMPLARY == "exemplary"

    # GapPriority (5)
    def test_priority_critical(self):
        assert GapPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert GapPriority.HIGH == "high"

    def test_priority_medium(self):
        assert GapPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert GapPriority.LOW == "low"

    def test_priority_informational(self):
        assert GapPriority.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_service_coverage_record_defaults(self):
        r = ServiceCoverageRecord()
        assert r.id
        assert r.service == ""
        assert r.pillar == ObservabilityPillar.LOGGING
        assert r.maturity == MaturityLevel.NONE
        assert r.coverage_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_coverage_gap_defaults(self):
        g = CoverageGap()
        assert g.id
        assert g.service == ""
        assert g.pillar == ObservabilityPillar.LOGGING
        assert g.priority == GapPriority.MEDIUM
        assert g.description == ""
        assert g.remediation == ""
        assert g.created_at > 0

    def test_observability_coverage_report_defaults(self):
        r = ObservabilityCoverageReport()
        assert r.total_records == 0
        assert r.total_gaps == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_pillar == {}
        assert r.by_maturity == {}
        assert r.services_below_threshold == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_coverage
# ---------------------------------------------------------------------------


class TestRecordCoverage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coverage(
            service="svc-a",
            pillar=ObservabilityPillar.LOGGING,
            coverage_pct=85.0,
        )
        assert r.service == "svc-a"
        assert r.pillar == ObservabilityPillar.LOGGING
        assert r.coverage_pct == 85.0
        assert r.maturity == MaturityLevel.ADVANCED

    def test_with_explicit_maturity(self):
        eng = _engine()
        r = eng.record_coverage(
            service="svc-b",
            pillar=ObservabilityPillar.METRICS,
            coverage_pct=50.0,
            maturity=MaturityLevel.EXEMPLARY,
            details="custom override",
        )
        assert r.maturity == MaturityLevel.EXEMPLARY
        assert r.details == "custom override"

    def test_auto_maturity_from_pct(self):
        eng = _engine()
        r = eng.record_coverage(
            service="svc-c", pillar=ObservabilityPillar.TRACING, coverage_pct=10.0
        )
        assert r.maturity == MaturityLevel.NONE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coverage(
                service=f"svc-{i}", pillar=ObservabilityPillar.LOGGING, coverage_pct=50.0
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------


class TestGetCoverage:
    def test_found(self):
        eng = _engine()
        r = eng.record_coverage(
            service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0
        )
        result = eng.get_coverage(r.id)
        assert result is not None
        assert result.service == "svc-a"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_coverage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_coverage
# ---------------------------------------------------------------------------


class TestListCoverage:
    def test_list_all(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0)
        eng.record_coverage(service="svc-b", pillar=ObservabilityPillar.METRICS, coverage_pct=70.0)
        assert len(eng.list_coverage()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0)
        eng.record_coverage(service="svc-b", pillar=ObservabilityPillar.METRICS, coverage_pct=70.0)
        results = eng.list_coverage(service="svc-a")
        assert len(results) == 1
        assert results[0].service == "svc-a"

    def test_filter_by_pillar(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0)
        eng.record_coverage(service="svc-b", pillar=ObservabilityPillar.METRICS, coverage_pct=70.0)
        results = eng.list_coverage(pillar=ObservabilityPillar.METRICS)
        assert len(results) == 1
        assert results[0].pillar == ObservabilityPillar.METRICS


# ---------------------------------------------------------------------------
# record_gap
# ---------------------------------------------------------------------------


class TestRecordGap:
    def test_basic(self):
        eng = _engine()
        g = eng.record_gap(
            service="svc-a",
            pillar=ObservabilityPillar.TRACING,
            priority=GapPriority.CRITICAL,
            description="No distributed tracing",
            remediation="Add OpenTelemetry SDK",
        )
        assert g.service == "svc-a"
        assert g.pillar == ObservabilityPillar.TRACING
        assert g.priority == GapPriority.CRITICAL
        assert g.description == "No distributed tracing"
        assert g.remediation == "Add OpenTelemetry SDK"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(service=f"svc-{i}", pillar=ObservabilityPillar.LOGGING)
        assert len(eng._gaps) == 3


# ---------------------------------------------------------------------------
# calculate_service_score
# ---------------------------------------------------------------------------


class TestCalculateServiceScore:
    def test_with_records(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0)
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.METRICS, coverage_pct=60.0)
        result = eng.calculate_service_score("svc-a")
        assert result["service"] == "svc-a"
        assert result["score"] == 70.0
        assert result["maturity"] == MaturityLevel.INTERMEDIATE.value
        assert result["pillar_count"] == 2
        assert "logging" in result["pillar_scores"]
        assert "metrics" in result["pillar_scores"]

    def test_no_records(self):
        eng = _engine()
        result = eng.calculate_service_score("unknown")
        assert result["score"] == 0.0
        assert result["maturity"] == "none"
        assert result["pillar_count"] == 0


# ---------------------------------------------------------------------------
# identify_instrumentation_gaps
# ---------------------------------------------------------------------------


class TestIdentifyInstrumentationGaps:
    def test_has_gaps(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=90.0)
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.METRICS, coverage_pct=80.0)
        # svc-a only has 2 of 5 pillars
        results = eng.identify_instrumentation_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"
        assert len(results[0]["missing_pillars"]) == 3
        assert "tracing" in results[0]["missing_pillars"]

    def test_all_pillars_covered(self):
        eng = _engine()
        for pillar in ObservabilityPillar:
            eng.record_coverage(service="svc-complete", pillar=pillar, coverage_pct=90.0)
        results = eng.identify_instrumentation_gaps()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# rank_services_by_coverage
# ---------------------------------------------------------------------------


class TestRankServicesByCoverage:
    def test_ranked(self):
        eng = _engine()
        eng.record_coverage(
            service="svc-high", pillar=ObservabilityPillar.LOGGING, coverage_pct=95.0
        )
        eng.record_coverage(
            service="svc-low", pillar=ObservabilityPillar.LOGGING, coverage_pct=30.0
        )
        results = eng.rank_services_by_coverage()
        assert len(results) == 2
        assert results[0]["service"] == "svc-high"
        assert results[1]["service"] == "svc-low"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_services_by_coverage() == []


# ---------------------------------------------------------------------------
# get_pillar_breakdown
# ---------------------------------------------------------------------------


class TestGetPillarBreakdown:
    def test_with_data(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0)
        eng.record_coverage(service="svc-b", pillar=ObservabilityPillar.LOGGING, coverage_pct=60.0)
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.METRICS, coverage_pct=90.0)
        result = eng.get_pillar_breakdown()
        assert result["total_services"] == 2
        assert result["total_records"] == 3
        assert result["pillar_averages"]["logging"] == 70.0
        assert result["pillar_averages"]["metrics"] == 90.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_pillar_breakdown()
        assert result["pillar_averages"] == {}
        assert result["total_services"] == 0
        assert result["total_records"] == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_coverage_pct=80.0)
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=90.0)
        eng.record_coverage(service="svc-b", pillar=ObservabilityPillar.METRICS, coverage_pct=40.0)
        eng.record_gap(
            service="svc-b", pillar=ObservabilityPillar.TRACING, priority=GapPriority.CRITICAL
        )
        report = eng.generate_report()
        assert isinstance(report, ObservabilityCoverageReport)
        assert report.total_records == 2
        assert report.total_gaps == 1
        assert report.avg_coverage_pct > 0
        assert len(report.by_pillar) > 0
        assert len(report.by_maturity) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.total_gaps == 0
        assert "Observability coverage meets targets" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=80.0)
        eng.record_gap(service="svc-a", pillar=ObservabilityPillar.TRACING)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["pillar_distribution"] == {}
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine(min_coverage_pct=80.0)
        eng.record_coverage(service="svc-a", pillar=ObservabilityPillar.LOGGING, coverage_pct=85.0)
        eng.record_gap(service="svc-a", pillar=ObservabilityPillar.TRACING)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_gaps"] == 1
        assert stats["min_coverage_pct"] == 80.0
        assert "logging" in stats["pillar_distribution"]
        assert stats["unique_services"] == 1

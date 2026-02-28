"""Tests for shieldops.sla.impact_analyzer — SLAImpactAnalyzer."""

from __future__ import annotations

from shieldops.sla.impact_analyzer import (
    ImpactContributor,
    ImpactRecord,
    ImpactSeverity,
    ImpactType,
    SLAImpactAnalyzer,
    SLAImpactReport,
    SLAStatus,
)


def _engine(**kw) -> SLAImpactAnalyzer:
    return SLAImpactAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ImpactType (5)
    def test_type_availability(self):
        assert ImpactType.AVAILABILITY == "availability"

    def test_type_latency(self):
        assert ImpactType.LATENCY == "latency"

    def test_type_error_rate(self):
        assert ImpactType.ERROR_RATE == "error_rate"

    def test_type_throughput(self):
        assert ImpactType.THROUGHPUT == "throughput"

    def test_type_data_loss(self):
        assert ImpactType.DATA_LOSS == "data_loss"

    # ImpactSeverity (5)
    def test_severity_catastrophic(self):
        assert ImpactSeverity.CATASTROPHIC == "catastrophic"

    def test_severity_major(self):
        assert ImpactSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_severity_negligible(self):
        assert ImpactSeverity.NEGLIGIBLE == "negligible"

    # SLAStatus (5)
    def test_status_healthy(self):
        assert SLAStatus.HEALTHY == "healthy"

    def test_status_at_risk(self):
        assert SLAStatus.AT_RISK == "at_risk"

    def test_status_breached(self):
        assert SLAStatus.BREACHED == "breached"

    def test_status_critical(self):
        assert SLAStatus.CRITICAL == "critical"

    def test_status_unknown(self):
        assert SLAStatus.UNKNOWN == "unknown"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_impact_record_defaults(self):
        r = ImpactRecord()
        assert r.id
        assert r.service == ""
        assert r.impact_type == ImpactType.AVAILABILITY
        assert r.severity == ImpactSeverity.NEGLIGIBLE
        assert r.sla_status == SLAStatus.UNKNOWN
        assert r.impact_score == 0.0
        assert r.duration_seconds == 0.0
        assert r.breached is False
        assert r.created_at > 0

    def test_impact_contributor_defaults(self):
        r = ImpactContributor()
        assert r.id
        assert r.contributor_name == ""
        assert r.impact_type == ImpactType.AVAILABILITY
        assert r.severity == ImpactSeverity.NEGLIGIBLE
        assert r.contribution_pct == 0.0
        assert r.service == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = SLAImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_contributors == 0
        assert r.breach_count == 0
        assert r.healthy_count == 0
        assert r.breach_rate_pct == 0.0
        assert r.by_impact_type == {}
        assert r.by_severity == {}
        assert r.by_sla_status == {}
        assert r.top_impacted_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_impact
# -------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact("payment-service")
        assert r.service == "payment-service"
        assert r.impact_type == ImpactType.AVAILABILITY

    def test_with_params(self):
        eng = _engine()
        r = eng.record_impact(
            "auth-service",
            impact_type=ImpactType.ERROR_RATE,
            severity=ImpactSeverity.CATASTROPHIC,
            sla_status=SLAStatus.BREACHED,
            impact_score=0.98,
            duration_seconds=3600.0,
            breached=True,
        )
        assert r.impact_type == ImpactType.ERROR_RATE
        assert r.severity == ImpactSeverity.CATASTROPHIC
        assert r.breached is True
        assert r.impact_score == 0.98

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_impact("svc-a")
        r2 = eng.record_impact("svc-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_impact
# -------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact("svc-x")
        assert eng.get_impact(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# -------------------------------------------------------------------
# list_impacts
# -------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact("svc-a")
        eng.record_impact("svc-b")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_impact_type(self):
        eng = _engine()
        eng.record_impact("svc-a", impact_type=ImpactType.LATENCY)
        eng.record_impact("svc-b", impact_type=ImpactType.THROUGHPUT)
        results = eng.list_impacts(impact_type=ImpactType.LATENCY)
        assert len(results) == 1
        assert results[0].impact_type == ImpactType.LATENCY

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_impact("svc-a", severity=ImpactSeverity.CATASTROPHIC)
        eng.record_impact("svc-b", severity=ImpactSeverity.NEGLIGIBLE)
        results = eng.list_impacts(severity=ImpactSeverity.CATASTROPHIC)
        assert len(results) == 1

    def test_filter_by_sla_status(self):
        eng = _engine()
        eng.record_impact("svc-a", sla_status=SLAStatus.BREACHED)
        eng.record_impact("svc-b", sla_status=SLAStatus.HEALTHY)
        results = eng.list_impacts(sla_status=SLAStatus.BREACHED)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(f"svc-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# -------------------------------------------------------------------
# add_contributor
# -------------------------------------------------------------------


class TestAddContributor:
    def test_basic(self):
        eng = _engine()
        c = eng.add_contributor("database-slowdown")
        assert c.contributor_name == "database-slowdown"
        assert c.impact_type == ImpactType.AVAILABILITY

    def test_with_params(self):
        eng = _engine()
        c = eng.add_contributor(
            "network-partition",
            impact_type=ImpactType.DATA_LOSS,
            severity=ImpactSeverity.MAJOR,
            contribution_pct=60.0,
            service="messaging-service",
        )
        assert c.impact_type == ImpactType.DATA_LOSS
        assert c.contribution_pct == 60.0

    def test_unique_contributor_ids(self):
        eng = _engine()
        c1 = eng.add_contributor("contrib-a")
        c2 = eng.add_contributor("contrib-b")
        assert c1.id != c2.id


# -------------------------------------------------------------------
# analyze_impact_by_service
# -------------------------------------------------------------------


class TestAnalyzeImpactByService:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_impact_by_service()
        assert result["total_services"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        for _ in range(4):
            eng.record_impact("checkout", breached=True)
        eng.record_impact("inventory", breached=False)
        result = eng.analyze_impact_by_service()
        assert result["total_services"] == 2
        services = [b["service"] for b in result["breakdown"]]
        assert "checkout" in services

    def test_sorted_by_breach_count(self):
        eng = _engine()
        for _ in range(2):
            eng.record_impact("low-breach", breached=True)
        for _ in range(6):
            eng.record_impact("high-breach", breached=True)
        result = eng.analyze_impact_by_service()
        assert result["breakdown"][0]["service"] == "high-breach"


# -------------------------------------------------------------------
# identify_sla_breaches
# -------------------------------------------------------------------


class TestIdentifySLABreaches:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_sla_breaches() == []

    def test_only_breached_returned(self):
        eng = _engine()
        eng.record_impact("svc-a", breached=False)
        eng.record_impact("svc-b", breached=True, severity=ImpactSeverity.CATASTROPHIC)
        results = eng.identify_sla_breaches()
        assert len(results) == 1
        assert results[0]["service"] == "svc-b"

    def test_sorted_by_severity(self):
        eng = _engine()
        eng.record_impact("svc-a", breached=True, severity=ImpactSeverity.MINOR)
        eng.record_impact("svc-b", breached=True, severity=ImpactSeverity.CATASTROPHIC)
        results = eng.identify_sla_breaches()
        assert results[0]["severity"] == "catastrophic"


# -------------------------------------------------------------------
# rank_by_impact_severity
# -------------------------------------------------------------------


class TestRankByImpactSeverity:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_severity() == []

    def test_sorted_by_score(self):
        eng = _engine()
        for _ in range(3):
            eng.record_impact("high-impact-svc", impact_score=0.95)
        eng.record_impact("low-impact-svc", impact_score=0.1)
        results = eng.rank_by_impact_severity()
        assert results[0]["service"] == "high-impact-svc"
        assert results[0]["avg_impact_score"] > results[-1]["avg_impact_score"]


# -------------------------------------------------------------------
# detect_impact_trends
# -------------------------------------------------------------------


class TestDetectImpactTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_impact("svc")
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(4):
            eng.record_impact("svc", breached=True)
        for _ in range(4):
            eng.record_impact("svc", breached=True)
        result = eng.detect_impact_trends()
        assert result["trend"] in ("stable", "improving", "worsening")

    def test_worsening_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_impact("svc", breached=False)
        for _ in range(8):
            eng.record_impact("svc", breached=True)
        result = eng.detect_impact_trends()
        assert result["trend"] == "worsening"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, SLAImpactReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.add_contributor("db-slowdown", service="payments")
        eng.record_impact("payments", breached=True, severity=ImpactSeverity.MAJOR)
        eng.record_impact("payments", breached=False, sla_status=SLAStatus.HEALTHY)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_contributors == 1
        assert report.breach_count == 1
        assert report.by_impact_type


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_contributors(self):
        eng = _engine()
        eng.record_impact("svc-a")
        eng.add_contributor("contrib-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._contributors) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_contributors"] == 0
        assert stats["breach_count"] == 0

    def test_populated(self):
        eng = _engine(max_breach_count=5.0)
        eng.record_impact(
            "svc-a",
            severity=ImpactSeverity.CATASTROPHIC,
            impact_score=0.9,
            breached=True,
        )
        eng.record_impact("svc-b", severity=ImpactSeverity.NEGLIGIBLE, impact_score=0.1)
        eng.add_contributor("contrib-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_contributors"] == 1
        assert stats["breach_count"] == 1
        assert stats["max_breach_count"] == 5.0
        assert stats["unique_services"] == 2
        assert stats["avg_impact_score"] > 0.0

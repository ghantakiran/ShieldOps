"""Tests for shieldops.security.vendor_sbom_tracker — VendorSBOMTracker."""

from __future__ import annotations

from shieldops.security.vendor_sbom_tracker import (
    SBOMCompleteness,
    UpdateFrequency,
    VendorSBOMAnalysis,
    VendorSBOMRecord,
    VendorSBOMReport,
    VendorSBOMTracker,
    VendorTier,
)


def _engine(**kw) -> VendorSBOMTracker:
    return VendorSBOMTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tier_strategic(self):
        assert VendorTier.STRATEGIC == "strategic"

    def test_tier_preferred(self):
        assert VendorTier.PREFERRED == "preferred"

    def test_tier_approved(self):
        assert VendorTier.APPROVED == "approved"

    def test_tier_conditional(self):
        assert VendorTier.CONDITIONAL == "conditional"

    def test_tier_blocked(self):
        assert VendorTier.BLOCKED == "blocked"

    def test_completeness_complete(self):
        assert SBOMCompleteness.COMPLETE == "complete"

    def test_completeness_substantial(self):
        assert SBOMCompleteness.SUBSTANTIAL == "substantial"

    def test_completeness_partial(self):
        assert SBOMCompleteness.PARTIAL == "partial"

    def test_completeness_minimal(self):
        assert SBOMCompleteness.MINIMAL == "minimal"

    def test_completeness_none(self):
        assert SBOMCompleteness.NONE == "none"

    def test_frequency_realtime(self):
        assert UpdateFrequency.REALTIME == "realtime"

    def test_frequency_daily(self):
        assert UpdateFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert UpdateFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert UpdateFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert UpdateFrequency.QUARTERLY == "quarterly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_vendor_sbom_record_defaults(self):
        r = VendorSBOMRecord()
        assert r.id
        assert r.vendor_name == ""
        assert r.vendor_tier == VendorTier.APPROVED
        assert r.sbom_completeness == SBOMCompleteness.COMPLETE
        assert r.update_frequency == UpdateFrequency.WEEKLY
        assert r.completeness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_vendor_sbom_analysis_defaults(self):
        c = VendorSBOMAnalysis()
        assert c.id
        assert c.vendor_name == ""
        assert c.vendor_tier == VendorTier.APPROVED
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_vendor_sbom_report_defaults(self):
        r = VendorSBOMReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_completeness_score == 0.0
        assert r.by_tier == {}
        assert r.by_completeness == {}
        assert r.by_frequency == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_vendor_sbom / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_vendor_sbom(
            vendor_name="AcmeCorp",
            vendor_tier=VendorTier.STRATEGIC,
            sbom_completeness=SBOMCompleteness.SUBSTANTIAL,
            update_frequency=UpdateFrequency.DAILY,
            completeness_score=85.0,
            service="procurement",
            team="security",
        )
        assert r.vendor_name == "AcmeCorp"
        assert r.vendor_tier == VendorTier.STRATEGIC
        assert r.sbom_completeness == SBOMCompleteness.SUBSTANTIAL
        assert r.update_frequency == UpdateFrequency.DAILY
        assert r.completeness_score == 85.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_vendor_sbom(vendor_name="WidgetInc", completeness_score=90.0)
        result = eng.get_vendor_sbom(r.id)
        assert result is not None
        assert result.completeness_score == 90.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_vendor_sbom("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_vendor_sbom(vendor_name=f"vendor-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_vendor_sboms
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_vendor_sbom(vendor_name="a")
        eng.record_vendor_sbom(vendor_name="b")
        assert len(eng.list_vendor_sboms()) == 2

    def test_filter_by_vendor_tier(self):
        eng = _engine()
        eng.record_vendor_sbom(vendor_name="a", vendor_tier=VendorTier.STRATEGIC)
        eng.record_vendor_sbom(vendor_name="b", vendor_tier=VendorTier.BLOCKED)
        results = eng.list_vendor_sboms(vendor_tier=VendorTier.STRATEGIC)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_vendor_sbom(vendor_name="a", team="security")
        eng.record_vendor_sbom(vendor_name="b", team="platform")
        results = eng.list_vendor_sboms(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_vendor_sbom(vendor_name=f"vendor-{i}")
        assert len(eng.list_vendor_sboms(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            vendor_name="AcmeCorp",
            vendor_tier=VendorTier.CONDITIONAL,
            analysis_score=35.0,
            threshold=60.0,
            breached=True,
            description="sbom incomplete",
        )
        assert a.vendor_name == "AcmeCorp"
        assert a.vendor_tier == VendorTier.CONDITIONAL
        assert a.analysis_score == 35.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(vendor_name=f"vendor-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_completeness(self):
        eng = _engine()
        eng.record_vendor_sbom(vendor_name="a", sbom_completeness=SBOMCompleteness.COMPLETE)
        eng.record_vendor_sbom(vendor_name="b", sbom_completeness=SBOMCompleteness.MINIMAL)
        results = eng.list_vendor_sboms(sbom_completeness=SBOMCompleteness.COMPLETE)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_tier_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_vendor_sbom(
            vendor_name="a", vendor_tier=VendorTier.STRATEGIC, completeness_score=90.0
        )
        eng.record_vendor_sbom(
            vendor_name="b", vendor_tier=VendorTier.STRATEGIC, completeness_score=70.0
        )
        result = eng.analyze_tier_distribution()
        assert "strategic" in result
        assert result["strategic"]["count"] == 2
        assert result["strategic"]["avg_completeness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_tier_distribution() == {}


# ---------------------------------------------------------------------------
# identify_completeness_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(completeness_gap_threshold=70.0)
        eng.record_vendor_sbom(vendor_name="a", completeness_score=50.0)
        eng.record_vendor_sbom(vendor_name="b", completeness_score=80.0)
        results = eng.identify_completeness_gaps()
        assert len(results) == 1
        assert results[0]["vendor_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(completeness_gap_threshold=80.0)
        eng.record_vendor_sbom(vendor_name="a", completeness_score=50.0)
        eng.record_vendor_sbom(vendor_name="b", completeness_score=20.0)
        results = eng.identify_completeness_gaps()
        assert len(results) == 2
        assert results[0]["completeness_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_vendor_sbom(vendor_name="a", service="proc", completeness_score=90.0)
        eng.record_vendor_sbom(vendor_name="b", service="risk", completeness_score=30.0)
        results = eng.rank_by_completeness()
        assert len(results) == 2
        assert results[0]["service"] == "risk"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_completeness_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(vendor_name="vendor", analysis_score=50.0)
        result = eng.detect_completeness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(vendor_name="v", analysis_score=20.0)
        eng.add_analysis(vendor_name="v", analysis_score=20.0)
        eng.add_analysis(vendor_name="v", analysis_score=80.0)
        eng.add_analysis(vendor_name="v", analysis_score=80.0)
        result = eng.detect_completeness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_completeness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(completeness_gap_threshold=60.0)
        eng.record_vendor_sbom(
            vendor_name="BadVendor",
            vendor_tier=VendorTier.CONDITIONAL,
            sbom_completeness=SBOMCompleteness.MINIMAL,
            completeness_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, VendorSBOMReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_vendor_sbom(vendor_name="v")
        eng.add_analysis(vendor_name="v")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_vendor_sbom(
            vendor_name="AcmeCorp",
            vendor_tier=VendorTier.STRATEGIC,
            service="proc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "strategic" in stats["tier_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_vendor_sbom(vendor_name=f"vendor-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].vendor_name == "vendor-4"

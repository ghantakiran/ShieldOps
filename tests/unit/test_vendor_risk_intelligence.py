"""Tests for shieldops.compliance.vendor_risk_intelligence — VendorRiskIntelligence."""

from __future__ import annotations

from shieldops.compliance.vendor_risk_intelligence import (
    AssessmentStatus,
    RiskDomain,
    VendorAnalysis,
    VendorRecord,
    VendorRiskIntelligence,
    VendorRiskReport,
    VendorTier,
)


def _engine(**kw) -> VendorRiskIntelligence:
    return VendorRiskIntelligence(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_vendortier_tier_1_critical(self):
        assert VendorTier.TIER_1_CRITICAL == "tier_1_critical"

    def test_vendortier_tier_2_important(self):
        assert VendorTier.TIER_2_IMPORTANT == "tier_2_important"

    def test_vendortier_tier_3_standard(self):
        assert VendorTier.TIER_3_STANDARD == "tier_3_standard"

    def test_vendortier_tier_4_low_risk(self):
        assert VendorTier.TIER_4_LOW_RISK == "tier_4_low_risk"

    def test_vendortier_tier_5_minimal(self):
        assert VendorTier.TIER_5_MINIMAL == "tier_5_minimal"

    def test_riskdomain_security(self):
        assert RiskDomain.SECURITY == "security"

    def test_riskdomain_compliance(self):
        assert RiskDomain.COMPLIANCE == "compliance"

    def test_riskdomain_financial(self):
        assert RiskDomain.FINANCIAL == "financial"

    def test_riskdomain_operational(self):
        assert RiskDomain.OPERATIONAL == "operational"

    def test_riskdomain_reputational(self):
        assert RiskDomain.REPUTATIONAL == "reputational"

    def test_assessmentstatus_completed(self):
        assert AssessmentStatus.COMPLETED == "completed"

    def test_assessmentstatus_in_progress(self):
        assert AssessmentStatus.IN_PROGRESS == "in_progress"

    def test_assessmentstatus_overdue(self):
        assert AssessmentStatus.OVERDUE == "overdue"

    def test_assessmentstatus_scheduled(self):
        assert AssessmentStatus.SCHEDULED == "scheduled"

    def test_assessmentstatus_not_started(self):
        assert AssessmentStatus.NOT_STARTED == "not_started"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_vendorrecord_defaults(self):
        r = VendorRecord()
        assert r.id
        assert r.vendor_name == ""
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_vendoranalysis_defaults(self):
        c = VendorAnalysis()
        assert c.id
        assert c.vendor_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_vendorriskreport_defaults(self):
        r = VendorRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_score == 0
        assert r.by_tier == {}
        assert r.by_domain == {}
        assert r.by_status == {}
        assert r.top_high_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_vendor
# ---------------------------------------------------------------------------


class TestRecordVendor:
    def test_basic(self):
        eng = _engine()
        r = eng.record_vendor(
            vendor_name="test-item",
            vendor_tier=VendorTier.TIER_2_IMPORTANT,
            risk_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.vendor_name == "test-item"
        assert r.risk_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_vendor(vendor_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_vendor
# ---------------------------------------------------------------------------


class TestGetVendor:
    def test_found(self):
        eng = _engine()
        r = eng.record_vendor(vendor_name="test-item")
        result = eng.get_vendor(r.id)
        assert result is not None
        assert result.vendor_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_vendor("nonexistent") is None


# ---------------------------------------------------------------------------
# list_vendors
# ---------------------------------------------------------------------------


class TestListVendors:
    def test_list_all(self):
        eng = _engine()
        eng.record_vendor(vendor_name="ITEM-001")
        eng.record_vendor(vendor_name="ITEM-002")
        assert len(eng.list_vendors()) == 2

    def test_filter_by_vendor_tier(self):
        eng = _engine()
        eng.record_vendor(vendor_name="ITEM-001", vendor_tier=VendorTier.TIER_1_CRITICAL)
        eng.record_vendor(vendor_name="ITEM-002", vendor_tier=VendorTier.TIER_2_IMPORTANT)
        results = eng.list_vendors(vendor_tier=VendorTier.TIER_1_CRITICAL)
        assert len(results) == 1

    def test_filter_by_risk_domain(self):
        eng = _engine()
        eng.record_vendor(vendor_name="ITEM-001", risk_domain=RiskDomain.SECURITY)
        eng.record_vendor(vendor_name="ITEM-002", risk_domain=RiskDomain.COMPLIANCE)
        results = eng.list_vendors(risk_domain=RiskDomain.SECURITY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_vendor(vendor_name="ITEM-001", team="security")
        eng.record_vendor(vendor_name="ITEM-002", team="platform")
        results = eng.list_vendors(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_vendor(vendor_name=f"ITEM-{i}")
        assert len(eng.list_vendors(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            vendor_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.vendor_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(vendor_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_tier_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_vendor(
            vendor_name="ITEM-001", vendor_tier=VendorTier.TIER_1_CRITICAL, risk_score=90.0
        )
        eng.record_vendor(
            vendor_name="ITEM-002", vendor_tier=VendorTier.TIER_1_CRITICAL, risk_score=70.0
        )
        result = eng.analyze_tier_distribution()
        assert "tier_1_critical" in result
        assert result["tier_1_critical"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_tier_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_vendors
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(vendor_risk_threshold=65.0)
        eng.record_vendor(vendor_name="ITEM-001", risk_score=90.0)
        eng.record_vendor(vendor_name="ITEM-002", risk_score=40.0)
        results = eng.identify_high_risk_vendors()
        assert len(results) == 1
        assert results[0]["vendor_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(vendor_risk_threshold=65.0)
        eng.record_vendor(vendor_name="ITEM-001", risk_score=80.0)
        eng.record_vendor(vendor_name="ITEM-002", risk_score=95.0)
        results = eng.identify_high_risk_vendors()
        assert len(results) == 2
        assert results[0]["risk_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_vendors() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_vendor(vendor_name="ITEM-001", service="auth-svc", risk_score=90.0)
        eng.record_vendor(vendor_name="ITEM-002", service="api-gw", risk_score=50.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(vendor_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(vendor_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(vendor_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(vendor_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(vendor_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(vendor_risk_threshold=65.0)
        eng.record_vendor(vendor_name="test-item", risk_score=90.0)
        report = eng.generate_report()
        assert isinstance(report, VendorRiskReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
        assert len(report.top_high_risk) == 1
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
        eng.record_vendor(vendor_name="ITEM-001")
        eng.add_analysis(vendor_name="ITEM-001")
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
        eng.record_vendor(
            vendor_name="ITEM-001",
            vendor_tier=VendorTier.TIER_1_CRITICAL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

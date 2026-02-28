"""Tests for shieldops.billing.vendor_lockin — VendorLockinAnalyzer."""

from __future__ import annotations

from shieldops.billing.vendor_lockin import (
    LockinAssessment,
    LockinCategory,
    LockinRecord,
    LockinRisk,
    MigrationComplexity,
    VendorLockinAnalyzer,
    VendorLockinReport,
)


def _engine(**kw) -> VendorLockinAnalyzer:
    return VendorLockinAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # LockinCategory (5)
    def test_category_compute(self):
        assert LockinCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert LockinCategory.STORAGE == "storage"

    def test_category_database(self):
        assert LockinCategory.DATABASE == "database"

    def test_category_networking(self):
        assert LockinCategory.NETWORKING == "networking"

    def test_category_proprietary_service(self):
        assert LockinCategory.PROPRIETARY_SERVICE == "proprietary_service"

    # LockinRisk (5)
    def test_risk_critical(self):
        assert LockinRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert LockinRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert LockinRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert LockinRisk.LOW == "low"

    def test_risk_minimal(self):
        assert LockinRisk.MINIMAL == "minimal"

    # MigrationComplexity (5)
    def test_complexity_extreme(self):
        assert MigrationComplexity.EXTREME == "extreme"

    def test_complexity_high(self):
        assert MigrationComplexity.HIGH == "high"

    def test_complexity_moderate(self):
        assert MigrationComplexity.MODERATE == "moderate"

    def test_complexity_low(self):
        assert MigrationComplexity.LOW == "low"

    def test_complexity_trivial(self):
        assert MigrationComplexity.TRIVIAL == "trivial"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_lockin_record_defaults(self):
        r = LockinRecord()
        assert r.id
        assert r.vendor_name == ""
        assert r.service_name == ""
        assert r.category == LockinCategory.COMPUTE
        assert r.risk == LockinRisk.MODERATE
        assert r.complexity == MigrationComplexity.MODERATE
        assert r.risk_score == 0.0
        assert r.monthly_spend == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_lockin_assessment_defaults(self):
        a = LockinAssessment()
        assert a.id
        assert a.vendor_name == ""
        assert a.category == LockinCategory.COMPUTE
        assert a.risk == LockinRisk.MODERATE
        assert a.complexity == MigrationComplexity.MODERATE
        assert a.estimated_exit_cost == 0.0
        assert a.notes == ""
        assert a.created_at > 0

    def test_vendor_lockin_report_defaults(self):
        r = VendorLockinReport()
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.avg_risk_score == 0.0
        assert r.by_category == {}
        assert r.by_risk == {}
        assert r.critical_lockin_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_lockin
# ---------------------------------------------------------------------------


class TestRecordLockin:
    def test_basic(self):
        eng = _engine()
        r = eng.record_lockin(
            vendor_name="AWS",
            service_name="RDS",
            category=LockinCategory.DATABASE,
            risk_score=75.0,
        )
        assert r.vendor_name == "AWS"
        assert r.service_name == "RDS"
        assert r.category == LockinCategory.DATABASE
        assert r.risk_score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lockin(vendor_name=f"v-{i}", service_name=f"svc-{i}")
        assert len(eng._records) == 3

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_lockin("AWS", "EC2")
        r2 = eng.record_lockin("GCP", "GCE")
        assert r1.id != r2.id


# ---------------------------------------------------------------------------
# get_lockin
# ---------------------------------------------------------------------------


class TestGetLockin:
    def test_found(self):
        eng = _engine()
        r = eng.record_lockin("AWS", "Lambda")
        assert eng.get_lockin(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_lockin("nonexistent") is None


# ---------------------------------------------------------------------------
# list_lockins
# ---------------------------------------------------------------------------


class TestListLockins:
    def test_list_all(self):
        eng = _engine()
        eng.record_lockin("AWS", "S3")
        eng.record_lockin("GCP", "GCS")
        assert len(eng.list_lockins()) == 2

    def test_filter_by_vendor(self):
        eng = _engine()
        eng.record_lockin("AWS", "S3")
        eng.record_lockin("GCP", "GCS")
        results = eng.list_lockins(vendor_name="AWS")
        assert len(results) == 1
        assert results[0].vendor_name == "AWS"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", category=LockinCategory.DATABASE)
        eng.record_lockin("AWS", "EC2", category=LockinCategory.COMPUTE)
        results = eng.list_lockins(category=LockinCategory.DATABASE)
        assert len(results) == 1
        assert results[0].category == LockinCategory.DATABASE


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            vendor_name="AWS",
            risk=LockinRisk.HIGH,
            estimated_exit_cost=50000.0,
        )
        assert a.vendor_name == "AWS"
        assert a.risk == LockinRisk.HIGH
        assert a.estimated_exit_cost == 50000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_assessment(vendor_name=f"v-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_lockin_by_vendor
# ---------------------------------------------------------------------------


class TestAnalyzeLockinByVendor:
    def test_with_data(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", risk_score=70.0, monthly_spend=1000.0)
        eng.record_lockin("AWS", "S3", risk_score=50.0, monthly_spend=500.0)
        result = eng.analyze_lockin_by_vendor("AWS")
        assert result["vendor_name"] == "AWS"
        assert result["total_services"] == 2
        assert result["avg_risk_score"] == 60.0
        assert result["total_monthly_spend"] == 1500.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_lockin_by_vendor("ghost")
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_critical_lockins
# ---------------------------------------------------------------------------


class TestIdentifyCriticalLockins:
    def test_with_critical(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", risk=LockinRisk.CRITICAL, risk_score=90.0)
        eng.record_lockin("GCP", "GCS", risk=LockinRisk.MINIMAL, risk_score=10.0)
        results = eng.identify_critical_lockins()
        assert len(results) == 1
        assert results[0]["risk"] == "critical"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_lockins() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", risk_score=90.0)
        eng.record_lockin("GCP", "GCS", risk_score=30.0)
        results = eng.rank_by_risk_score()
        assert results[0]["risk_score"] == 90.0
        assert results[1]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_lockin_trends
# ---------------------------------------------------------------------------


class TestDetectLockinTrends:
    def test_with_trend(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", risk_score=40.0)
        eng.record_lockin("AWS", "S3", risk_score=80.0)
        trends = eng.detect_lockin_trends()
        assert len(trends) == 1
        assert trends[0]["vendor_name"] == "AWS"
        assert trends[0]["trending_up"] is True

    def test_single_record_no_trend(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", risk_score=50.0)
        trends = eng.detect_lockin_trends()
        assert len(trends) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_risk_score=80.0)
        eng.record_lockin("AWS", "RDS", risk=LockinRisk.CRITICAL, risk_score=85.0)
        eng.add_assessment("AWS")
        report = eng.generate_report()
        assert isinstance(report, VendorLockinReport)
        assert report.total_records == 1
        assert report.total_assessments == 1
        assert report.critical_lockin_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable thresholds" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS")
        eng.add_assessment("AWS")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["category_distribution"] == {}
        assert stats["unique_vendors"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_lockin("AWS", "RDS", category=LockinCategory.DATABASE)
        eng.record_lockin("GCP", "GCS", category=LockinCategory.STORAGE)
        eng.add_assessment("AWS")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_assessments"] == 1
        assert stats["unique_vendors"] == 2
        assert "database" in stats["category_distribution"]

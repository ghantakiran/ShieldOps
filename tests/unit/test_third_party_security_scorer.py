"""Tests for shieldops.compliance.third_party_security_scorer — ThirdPartySecurityScorer."""

from __future__ import annotations

from shieldops.compliance.third_party_security_scorer import (
    AssessmentType,
    SecurityRating,
    ThirdPartySecurityScorer,
    VendorAnalysis,
    VendorRecord,
    VendorSecurityReport,
    VendorTier,
)


def _engine(**kw) -> ThirdPartySecurityScorer:
    return ThirdPartySecurityScorer(**kw)


class TestEnums:
    def test_tier_critical(self):
        assert VendorTier.CRITICAL == "critical"

    def test_tier_high(self):
        assert VendorTier.HIGH == "high"

    def test_tier_medium(self):
        assert VendorTier.MEDIUM == "medium"

    def test_tier_low(self):
        assert VendorTier.LOW == "low"

    def test_tier_minimal(self):
        assert VendorTier.MINIMAL == "minimal"

    def test_assessment_questionnaire(self):
        assert AssessmentType.QUESTIONNAIRE == "questionnaire"

    def test_assessment_audit(self):
        assert AssessmentType.AUDIT == "audit"

    def test_assessment_continuous_monitoring(self):
        assert AssessmentType.CONTINUOUS_MONITORING == "continuous_monitoring"

    def test_assessment_penetration_test(self):
        assert AssessmentType.PENETRATION_TEST == "penetration_test"

    def test_assessment_certification(self):
        assert AssessmentType.CERTIFICATION == "certification"

    def test_rating_excellent(self):
        assert SecurityRating.EXCELLENT == "excellent"

    def test_rating_good(self):
        assert SecurityRating.GOOD == "good"

    def test_rating_acceptable(self):
        assert SecurityRating.ACCEPTABLE == "acceptable"

    def test_rating_poor(self):
        assert SecurityRating.POOR == "poor"

    def test_rating_critical(self):
        assert SecurityRating.CRITICAL == "critical"


class TestModels:
    def test_record_defaults(self):
        r = VendorRecord()
        assert r.id
        assert r.vendor_name == ""
        assert r.vendor_tier == VendorTier.CRITICAL
        assert r.assessment_type == AssessmentType.QUESTIONNAIRE
        assert r.security_rating == SecurityRating.EXCELLENT
        assert r.vendor_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = VendorAnalysis()
        assert a.id
        assert a.vendor_name == ""
        assert a.vendor_tier == VendorTier.CRITICAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = VendorSecurityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_vendor_score == 0.0
        assert r.by_tier == {}
        assert r.by_assessment == {}
        assert r.by_rating == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_vendor(
            vendor_name="cloud-provider-x",
            vendor_tier=VendorTier.CRITICAL,
            assessment_type=AssessmentType.AUDIT,
            security_rating=SecurityRating.GOOD,
            vendor_score=85.0,
            service="vendor-mgmt",
            team="procurement",
        )
        assert r.vendor_name == "cloud-provider-x"
        assert r.vendor_tier == VendorTier.CRITICAL
        assert r.vendor_score == 85.0
        assert r.service == "vendor-mgmt"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_vendor(vendor_name=f"vendor-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_vendor(vendor_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_vendor(vendor_name="a")
        eng.record_vendor(vendor_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_vendor_tier(self):
        eng = _engine()
        eng.record_vendor(vendor_name="a", vendor_tier=VendorTier.CRITICAL)
        eng.record_vendor(vendor_name="b", vendor_tier=VendorTier.LOW)
        assert len(eng.list_records(vendor_tier=VendorTier.CRITICAL)) == 1

    def test_filter_by_security_rating(self):
        eng = _engine()
        eng.record_vendor(vendor_name="a", security_rating=SecurityRating.EXCELLENT)
        eng.record_vendor(vendor_name="b", security_rating=SecurityRating.POOR)
        assert len(eng.list_records(security_rating=SecurityRating.EXCELLENT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_vendor(vendor_name="a", team="sec")
        eng.record_vendor(vendor_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_vendor(vendor_name=f"v-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            vendor_name="test",
            analysis_score=88.5,
            breached=True,
            description="vendor risk",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(vendor_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_vendor(vendor_name="a", vendor_tier=VendorTier.CRITICAL, vendor_score=90.0)
        eng.record_vendor(vendor_name="b", vendor_tier=VendorTier.CRITICAL, vendor_score=70.0)
        result = eng.analyze_distribution()
        assert "critical" in result
        assert result["critical"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_vendor(vendor_name="a", vendor_score=60.0)
        eng.record_vendor(vendor_name="b", vendor_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_vendor(vendor_name="a", vendor_score=50.0)
        eng.record_vendor(vendor_name="b", vendor_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["vendor_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_vendor(vendor_name="a", service="auth", vendor_score=90.0)
        eng.record_vendor(vendor_name="b", service="api", vendor_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(vendor_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(vendor_name="a", analysis_score=20.0)
        eng.add_analysis(vendor_name="b", analysis_score=20.0)
        eng.add_analysis(vendor_name="c", analysis_score=80.0)
        eng.add_analysis(vendor_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_vendor(vendor_name="test", vendor_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_vendor(vendor_name="test")
        eng.add_analysis(vendor_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_vendor(vendor_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

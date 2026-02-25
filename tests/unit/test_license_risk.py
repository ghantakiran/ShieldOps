"""Tests for shieldops.compliance.license_risk — DependencyLicenseRiskAnalyzer."""

from __future__ import annotations

from shieldops.compliance.license_risk import (
    CompatibilityStatus,
    DependencyLicenseRiskAnalyzer,
    LicenseCategory,
    LicenseConflict,
    LicenseRiskRecord,
    LicenseRiskReport,
    RiskLevel,
)


def _engine(**kw) -> DependencyLicenseRiskAnalyzer:
    return DependencyLicenseRiskAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # LicenseCategory (5)
    def test_category_permissive(self):
        assert LicenseCategory.PERMISSIVE == "permissive"

    def test_category_weak_copyleft(self):
        assert LicenseCategory.WEAK_COPYLEFT == "weak_copyleft"

    def test_category_strong_copyleft(self):
        assert LicenseCategory.STRONG_COPYLEFT == "strong_copyleft"

    def test_category_proprietary(self):
        assert LicenseCategory.PROPRIETARY == "proprietary"

    def test_category_unknown(self):
        assert LicenseCategory.UNKNOWN == "unknown"

    # CompatibilityStatus (5)
    def test_compat_compatible(self):
        assert CompatibilityStatus.COMPATIBLE == "compatible"

    def test_compat_conditional(self):
        assert CompatibilityStatus.CONDITIONAL == "conditional"

    def test_compat_incompatible(self):
        assert CompatibilityStatus.INCOMPATIBLE == "incompatible"

    def test_compat_requires_review(self):
        assert CompatibilityStatus.REQUIRES_REVIEW == "requires_review"

    def test_compat_unassessed(self):
        assert CompatibilityStatus.UNASSESSED == "unassessed"

    # RiskLevel (5)
    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_acceptable(self):
        assert RiskLevel.ACCEPTABLE == "acceptable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_license_risk_record_defaults(self):
        r = LicenseRiskRecord()
        assert r.id
        assert r.package_name == ""
        assert r.version == ""
        assert r.license_name == ""
        assert r.category == LicenseCategory.UNKNOWN
        assert r.risk_level == RiskLevel.MEDIUM
        assert r.transitive_depth == 0
        assert r.compatibility == CompatibilityStatus.UNASSESSED
        assert r.details == ""
        assert r.created_at > 0

    def test_license_conflict_defaults(self):
        r = LicenseConflict()
        assert r.id
        assert r.package_a == ""
        assert r.package_b == ""
        assert r.license_a == ""
        assert r.license_b == ""
        assert r.conflict_reason == ""
        assert r.risk_level == RiskLevel.HIGH
        assert r.details == ""
        assert r.created_at > 0

    def test_license_risk_report_defaults(self):
        r = LicenseRiskReport()
        assert r.total_licenses == 0
        assert r.total_conflicts == 0
        assert r.by_category == {}
        assert r.by_risk_level == {}
        assert r.copyleft_count == 0
        assert r.conflict_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_license
# -------------------------------------------------------------------


class TestRecordLicense:
    def test_basic(self):
        eng = _engine()
        r = eng.record_license(
            "requests",
            version="2.31.0",
            license_name="Apache-2.0",
            category=LicenseCategory.PERMISSIVE,
        )
        assert r.package_name == "requests"
        assert r.version == "2.31.0"
        assert r.category == LicenseCategory.PERMISSIVE

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_license(
            "libgpl",
            version="1.0.0",
            license_name="GPL-3.0",
            category=LicenseCategory.STRONG_COPYLEFT,
            risk_level=RiskLevel.CRITICAL,
            transitive_depth=3,
            compatibility=CompatibilityStatus.INCOMPATIBLE,
            details="strong copyleft",
        )
        assert r.risk_level == RiskLevel.CRITICAL
        assert r.transitive_depth == 3
        assert r.compatibility == CompatibilityStatus.INCOMPATIBLE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_license(f"pkg-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_license
# -------------------------------------------------------------------


class TestGetLicense:
    def test_found(self):
        eng = _engine()
        r = eng.record_license("requests")
        assert eng.get_license(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_license("nonexistent") is None


# -------------------------------------------------------------------
# list_licenses
# -------------------------------------------------------------------


class TestListLicenses:
    def test_list_all(self):
        eng = _engine()
        eng.record_license("pkg-a")
        eng.record_license("pkg-b")
        assert len(eng.list_licenses()) == 2

    def test_filter_by_package_name(self):
        eng = _engine()
        eng.record_license("pkg-a")
        eng.record_license("pkg-b")
        results = eng.list_licenses(package_name="pkg-a")
        assert len(results) == 1
        assert results[0].package_name == "pkg-a"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_license("p1", category=LicenseCategory.PERMISSIVE)
        eng.record_license("p2", category=LicenseCategory.PROPRIETARY)
        results = eng.list_licenses(category=LicenseCategory.PERMISSIVE)
        assert len(results) == 1
        assert results[0].package_name == "p1"


# -------------------------------------------------------------------
# record_conflict
# -------------------------------------------------------------------


class TestRecordConflict:
    def test_basic(self):
        eng = _engine()
        c = eng.record_conflict(
            "pkg-a",
            "pkg-b",
            license_a="MIT",
            license_b="GPL-3.0",
            conflict_reason="Copyleft incompatibility",
        )
        assert c.package_a == "pkg-a"
        assert c.package_b == "pkg-b"
        assert c.conflict_reason == "Copyleft incompatibility"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_conflict(f"a-{i}", f"b-{i}")
        assert len(eng._conflicts) == 2


# -------------------------------------------------------------------
# analyze_license_risk
# -------------------------------------------------------------------


class TestAnalyzeLicenseRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_license(
            "requests",
            license_name="Apache-2.0",
            category=LicenseCategory.PERMISSIVE,
            risk_level=RiskLevel.LOW,
            transitive_depth=1,
            compatibility=CompatibilityStatus.COMPATIBLE,
        )
        result = eng.analyze_license_risk("requests")
        assert result["package_name"] == "requests"
        assert result["license_name"] == "Apache-2.0"
        assert result["category"] == "permissive"
        assert result["risk_level"] == "low"
        assert result["transitive_depth"] == 1
        assert result["compatibility"] == "compatible"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_license_risk("ghost-pkg")
        assert result["package_name"] == "ghost-pkg"
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_copyleft_contamination
# -------------------------------------------------------------------


class TestIdentifyCopyleftContamination:
    def test_with_copyleft(self):
        eng = _engine()
        eng.record_license("pkg-a", category=LicenseCategory.PERMISSIVE)
        eng.record_license(
            "pkg-b",
            category=LicenseCategory.WEAK_COPYLEFT,
            license_name="LGPL-2.1",
            transitive_depth=2,
        )
        eng.record_license(
            "pkg-c",
            category=LicenseCategory.STRONG_COPYLEFT,
            license_name="GPL-3.0",
            transitive_depth=1,
        )
        results = eng.identify_copyleft_contamination()
        assert len(results) == 2
        # Sorted by transitive_depth ascending
        assert results[0]["package_name"] == "pkg-c"
        assert results[0]["transitive_depth"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_copyleft_contamination() == []


# -------------------------------------------------------------------
# detect_license_conflicts
# -------------------------------------------------------------------


class TestDetectLicenseConflicts:
    def test_with_conflicts(self):
        eng = _engine()
        eng.record_conflict(
            "a",
            "b",
            license_a="MIT",
            license_b="GPL-3.0",
            risk_level=RiskLevel.HIGH,
        )
        eng.record_conflict(
            "c",
            "d",
            license_a="Apache-2.0",
            license_b="AGPL-3.0",
            risk_level=RiskLevel.CRITICAL,
        )
        results = eng.detect_license_conflicts()
        assert len(results) == 2
        # Sorted by risk_level severity (critical first)
        assert results[0]["risk_level"] == "critical"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_license_conflicts() == []


# -------------------------------------------------------------------
# rank_by_risk
# -------------------------------------------------------------------


class TestRankByRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_license("p1", risk_level=RiskLevel.LOW)
        eng.record_license("p2", risk_level=RiskLevel.CRITICAL)
        eng.record_license("p3", risk_level=RiskLevel.MEDIUM)
        results = eng.rank_by_risk()
        assert len(results) == 3
        assert results[0]["risk_level"] == "critical"
        assert results[1]["risk_level"] == "medium"
        assert results[2]["risk_level"] == "low"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_license("p1", category=LicenseCategory.PERMISSIVE, risk_level=RiskLevel.LOW)
        eng.record_license(
            "p2", category=LicenseCategory.STRONG_COPYLEFT, risk_level=RiskLevel.HIGH
        )
        eng.record_conflict("p1", "p2")
        report = eng.generate_report()
        assert report.total_licenses == 2
        assert report.total_conflicts == 1
        assert report.by_category != {}
        assert report.by_risk_level != {}
        assert report.copyleft_count == 1
        assert report.conflict_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_licenses == 0
        assert report.copyleft_count == 0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_license("p1")
        eng.record_conflict("p1", "p2")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._conflicts) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_licenses"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_license("p1", category=LicenseCategory.PERMISSIVE)
        eng.record_license("p2", category=LicenseCategory.PROPRIETARY)
        eng.record_conflict("p1", "p2")
        stats = eng.get_stats()
        assert stats["total_licenses"] == 2
        assert stats["total_conflicts"] == 1
        assert stats["unique_packages"] == 2
        assert stats["max_transitive_depth"] == 5

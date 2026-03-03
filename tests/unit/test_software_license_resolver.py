"""Tests for shieldops.compliance.software_license_resolver — SoftwareLicenseResolver."""

from __future__ import annotations

from shieldops.compliance.software_license_resolver import (
    ConflictSeverity,
    LicenseResolution,
    LicenseResolutionReport,
    LicenseType,
    ResolutionAnalysis,
    ResolutionStrategy,
    SoftwareLicenseResolver,
)


def _engine(**kw) -> SoftwareLicenseResolver:
    return SoftwareLicenseResolver(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_permissive(self):
        assert LicenseType.PERMISSIVE == "permissive"

    def test_type_copyleft(self):
        assert LicenseType.COPYLEFT == "copyleft"

    def test_type_weak_copyleft(self):
        assert LicenseType.WEAK_COPYLEFT == "weak_copyleft"

    def test_type_proprietary(self):
        assert LicenseType.PROPRIETARY == "proprietary"

    def test_type_unknown(self):
        assert LicenseType.UNKNOWN == "unknown"

    def test_severity_critical(self):
        assert ConflictSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ConflictSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert ConflictSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert ConflictSeverity.LOW == "low"

    def test_severity_none(self):
        assert ConflictSeverity.NONE == "none"

    def test_strategy_replace(self):
        assert ResolutionStrategy.REPLACE == "replace"

    def test_strategy_waiver(self):
        assert ResolutionStrategy.WAIVER == "waiver"

    def test_strategy_dual_license(self):
        assert ResolutionStrategy.DUAL_LICENSE == "dual_license"

    def test_strategy_remove(self):
        assert ResolutionStrategy.REMOVE == "remove"

    def test_strategy_accept(self):
        assert ResolutionStrategy.ACCEPT == "accept"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_license_resolution_defaults(self):
        r = LicenseResolution()
        assert r.id
        assert r.package_name == ""
        assert r.license_type == LicenseType.PERMISSIVE
        assert r.conflict_severity == ConflictSeverity.NONE
        assert r.resolution_strategy == ResolutionStrategy.ACCEPT
        assert r.compliance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_resolution_analysis_defaults(self):
        c = ResolutionAnalysis()
        assert c.id
        assert c.package_name == ""
        assert c.license_type == LicenseType.PERMISSIVE
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_license_resolution_report_defaults(self):
        r = LicenseResolutionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_license_type == {}
        assert r.by_severity == {}
        assert r.by_strategy == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_resolution / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_resolution(
            package_name="gpl-lib",
            license_type=LicenseType.COPYLEFT,
            conflict_severity=ConflictSeverity.HIGH,
            resolution_strategy=ResolutionStrategy.REPLACE,
            compliance_score=45.0,
            service="backend",
            team="legal",
        )
        assert r.package_name == "gpl-lib"
        assert r.license_type == LicenseType.COPYLEFT
        assert r.conflict_severity == ConflictSeverity.HIGH
        assert r.resolution_strategy == ResolutionStrategy.REPLACE
        assert r.compliance_score == 45.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_resolution(package_name="mit-lib", compliance_score=95.0)
        result = eng.get_resolution(r.id)
        assert result is not None
        assert result.compliance_score == 95.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_resolution("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_resolution(package_name=f"pkg-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_resolutions
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_resolution(package_name="a")
        eng.record_resolution(package_name="b")
        assert len(eng.list_resolutions()) == 2

    def test_filter_by_license_type(self):
        eng = _engine()
        eng.record_resolution(package_name="a", license_type=LicenseType.PERMISSIVE)
        eng.record_resolution(package_name="b", license_type=LicenseType.COPYLEFT)
        results = eng.list_resolutions(license_type=LicenseType.PERMISSIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_resolution(package_name="a", team="legal")
        eng.record_resolution(package_name="b", team="platform")
        results = eng.list_resolutions(team="legal")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_resolution(package_name=f"pkg-{i}")
        assert len(eng.list_resolutions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            package_name="gpl-lib",
            license_type=LicenseType.COPYLEFT,
            analysis_score=40.0,
            threshold=60.0,
            breached=True,
            description="license conflict detected",
        )
        assert a.package_name == "gpl-lib"
        assert a.license_type == LicenseType.COPYLEFT
        assert a.analysis_score == 40.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(package_name=f"pkg-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_conflict_severity(self):
        eng = _engine()
        eng.record_resolution(package_name="a", conflict_severity=ConflictSeverity.HIGH)
        eng.record_resolution(package_name="b", conflict_severity=ConflictSeverity.NONE)
        results = eng.list_resolutions(conflict_severity=ConflictSeverity.HIGH)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_license_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_resolution(
            package_name="a", license_type=LicenseType.PERMISSIVE, compliance_score=90.0
        )
        eng.record_resolution(
            package_name="b", license_type=LicenseType.PERMISSIVE, compliance_score=70.0
        )
        result = eng.analyze_license_distribution()
        assert "permissive" in result
        assert result["permissive"]["count"] == 2
        assert result["permissive"]["avg_compliance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_license_distribution() == {}


# ---------------------------------------------------------------------------
# identify_license_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(compliance_gap_threshold=70.0)
        eng.record_resolution(package_name="a", compliance_score=50.0)
        eng.record_resolution(package_name="b", compliance_score=90.0)
        results = eng.identify_license_gaps()
        assert len(results) == 1
        assert results[0]["package_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_resolution(package_name="a", compliance_score=50.0)
        eng.record_resolution(package_name="b", compliance_score=30.0)
        results = eng.identify_license_gaps()
        assert len(results) == 2
        assert results[0]["compliance_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_resolution(package_name="a", service="backend", compliance_score=90.0)
        eng.record_resolution(package_name="b", service="frontend", compliance_score=50.0)
        results = eng.rank_by_compliance()
        assert len(results) == 2
        assert results[0]["service"] == "frontend"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(package_name="pkg", analysis_score=50.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(compliance_gap_threshold=70.0)
        eng.record_resolution(
            package_name="gpl-lib",
            license_type=LicenseType.COPYLEFT,
            conflict_severity=ConflictSeverity.HIGH,
            compliance_score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, LicenseResolutionReport)
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
        eng.record_resolution(package_name="pkg")
        eng.add_analysis(package_name="pkg")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_resolution(
            package_name="mit-lib",
            license_type=LicenseType.PERMISSIVE,
            service="backend",
            team="legal",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "permissive" in stats["license_type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_resolution(package_name=f"pkg-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].package_name == "pkg-4"

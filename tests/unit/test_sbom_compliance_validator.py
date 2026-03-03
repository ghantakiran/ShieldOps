"""Tests for shieldops.security.sbom_compliance_validator — SBOMComplianceValidator."""

from __future__ import annotations

from shieldops.security.sbom_compliance_validator import (
    ComplianceAnalysis,
    ComplianceLevel,
    SBOMComplianceReport,
    SBOMComplianceValidator,
    SBOMFormat,
    SBOMValidation,
    ValidationScope,
)


def _engine(**kw) -> SBOMComplianceValidator:
    return SBOMComplianceValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_format_spdx(self):
        assert SBOMFormat.SPDX == "spdx"

    def test_format_cyclonedx(self):
        assert SBOMFormat.CYCLONEDX == "cyclonedx"

    def test_format_swid(self):
        assert SBOMFormat.SWID == "swid"

    def test_format_csv(self):
        assert SBOMFormat.CSV == "csv"

    def test_format_custom(self):
        assert SBOMFormat.CUSTOM == "custom"

    def test_level_full(self):
        assert ComplianceLevel.FULL == "full"

    def test_level_partial(self):
        assert ComplianceLevel.PARTIAL == "partial"

    def test_level_minimal(self):
        assert ComplianceLevel.MINIMAL == "minimal"

    def test_level_none(self):
        assert ComplianceLevel.NONE == "none"

    def test_level_unknown(self):
        assert ComplianceLevel.UNKNOWN == "unknown"

    def test_scope_direct(self):
        assert ValidationScope.DIRECT == "direct"

    def test_scope_transitive(self):
        assert ValidationScope.TRANSITIVE == "transitive"

    def test_scope_dev(self):
        assert ValidationScope.DEV == "dev"

    def test_scope_optional(self):
        assert ValidationScope.OPTIONAL == "optional"

    def test_scope_all(self):
        assert ValidationScope.ALL == "all"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_sbom_validation_defaults(self):
        r = SBOMValidation()
        assert r.id
        assert r.component_name == ""
        assert r.sbom_format == SBOMFormat.SPDX
        assert r.compliance_level == ComplianceLevel.FULL
        assert r.validation_scope == ValidationScope.ALL
        assert r.compliance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_compliance_analysis_defaults(self):
        c = ComplianceAnalysis()
        assert c.id
        assert c.component_name == ""
        assert c.sbom_format == SBOMFormat.SPDX
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_sbom_compliance_report_defaults(self):
        r = SBOMComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_format == {}
        assert r.by_level == {}
        assert r.by_scope == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_validation / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_validation(
            component_name="log4j",
            sbom_format=SBOMFormat.CYCLONEDX,
            compliance_level=ComplianceLevel.PARTIAL,
            validation_scope=ValidationScope.TRANSITIVE,
            compliance_score=72.0,
            service="auth-svc",
            team="security",
        )
        assert r.component_name == "log4j"
        assert r.sbom_format == SBOMFormat.CYCLONEDX
        assert r.compliance_level == ComplianceLevel.PARTIAL
        assert r.validation_scope == ValidationScope.TRANSITIVE
        assert r.compliance_score == 72.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_validation(component_name="requests", compliance_score=90.0)
        result = eng.get_validation(r.id)
        assert result is not None
        assert result.compliance_score == 90.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(component_name=f"pkg-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_validations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation(component_name="pkg-a")
        eng.record_validation(component_name="pkg-b")
        assert len(eng.list_validations()) == 2

    def test_filter_by_sbom_format(self):
        eng = _engine()
        eng.record_validation(component_name="a", sbom_format=SBOMFormat.SPDX)
        eng.record_validation(component_name="b", sbom_format=SBOMFormat.CYCLONEDX)
        results = eng.list_validations(sbom_format=SBOMFormat.SPDX)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_validation(component_name="a", team="security")
        eng.record_validation(component_name="b", team="platform")
        results = eng.list_validations(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(component_name=f"pkg-{i}")
        assert len(eng.list_validations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            component_name="requests",
            sbom_format=SBOMFormat.SPDX,
            analysis_score=85.0,
            threshold=80.0,
            breached=True,
            description="partial sbom detected",
        )
        assert a.component_name == "requests"
        assert a.sbom_format == SBOMFormat.SPDX
        assert a.analysis_score == 85.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(component_name=f"pkg-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_compliance_level(self):
        eng = _engine()
        eng.record_validation(component_name="a", compliance_level=ComplianceLevel.FULL)
        eng.record_validation(component_name="b", compliance_level=ComplianceLevel.MINIMAL)
        results = eng.list_validations(compliance_level=ComplianceLevel.FULL)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_format_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation(
            component_name="a", sbom_format=SBOMFormat.SPDX, compliance_score=90.0
        )
        eng.record_validation(
            component_name="b", sbom_format=SBOMFormat.SPDX, compliance_score=70.0
        )
        result = eng.analyze_format_distribution()
        assert "spdx" in result
        assert result["spdx"]["count"] == 2
        assert result["spdx"]["avg_compliance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_format_distribution() == {}


# ---------------------------------------------------------------------------
# identify_compliance_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_validation(component_name="a", compliance_score=60.0)
        eng.record_validation(component_name="b", compliance_score=90.0)
        results = eng.identify_compliance_gaps()
        assert len(results) == 1
        assert results[0]["component_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_validation(component_name="a", compliance_score=50.0)
        eng.record_validation(component_name="b", compliance_score=30.0)
        results = eng.identify_compliance_gaps()
        assert len(results) == 2
        assert results[0]["compliance_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_validation(component_name="a", service="auth-svc", compliance_score=90.0)
        eng.record_validation(component_name="b", service="api-gw", compliance_score=50.0)
        results = eng.rank_by_compliance()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_compliance_score"] == 50.0

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
            eng.add_analysis(component_name="pkg", analysis_score=50.0)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(component_name="pkg", analysis_score=20.0)
        eng.add_analysis(component_name="pkg", analysis_score=20.0)
        eng.add_analysis(component_name="pkg", analysis_score=80.0)
        eng.add_analysis(component_name="pkg", analysis_score=80.0)
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
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_validation(
            component_name="log4j",
            sbom_format=SBOMFormat.CYCLONEDX,
            compliance_level=ComplianceLevel.PARTIAL,
            compliance_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SBOMComplianceReport)
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
        eng.record_validation(component_name="pkg")
        eng.add_analysis(component_name="pkg")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_validation(
            component_name="pkg",
            sbom_format=SBOMFormat.SPDX,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "spdx" in stats["format_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_validation(component_name=f"pkg-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].component_name == "pkg-4"

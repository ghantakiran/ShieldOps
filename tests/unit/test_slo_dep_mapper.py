"""Tests for shieldops.sla.slo_dep_mapper — SLODependencyMapper."""

from __future__ import annotations

from shieldops.sla.slo_dep_mapper import (
    DependencyType,
    MappingRecord,
    MappingRule,
    MappingStatus,
    RiskLevel,
    SLODependencyMapper,
    SLODependencyReport,
)


def _engine(**kw) -> SLODependencyMapper:
    return SLODependencyMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_mapped(self):
        assert MappingStatus.MAPPED == "mapped"

    def test_status_unmapped(self):
        assert MappingStatus.UNMAPPED == "unmapped"

    def test_status_partial(self):
        assert MappingStatus.PARTIAL == "partial"

    def test_status_stale(self):
        assert MappingStatus.STALE == "stale"

    def test_status_conflicting(self):
        assert MappingStatus.CONFLICTING == "conflicting"

    def test_type_hard(self):
        assert DependencyType.HARD == "hard"

    def test_type_soft(self):
        assert DependencyType.SOFT == "soft"

    def test_type_optional(self):
        assert DependencyType.OPTIONAL == "optional"

    def test_type_transitive(self):
        assert DependencyType.TRANSITIVE == "transitive"

    def test_type_circular(self):
        assert DependencyType.CIRCULAR == "circular"

    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_none(self):
        assert RiskLevel.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_mapping_record_defaults(self):
        r = MappingRecord()
        assert r.id
        assert r.service == ""
        assert r.dependency_service == ""
        assert r.mapping_status == MappingStatus.UNMAPPED
        assert r.dependency_type == DependencyType.HARD
        assert r.risk_level == RiskLevel.NONE
        assert r.slo_target_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_mapping_rule_defaults(self):
        r = MappingRule()
        assert r.id
        assert r.service_pattern == ""
        assert r.mapping_status == MappingStatus.UNMAPPED
        assert r.dependency_type == DependencyType.HARD
        assert r.min_slo_pct == 0.0
        assert r.reason == ""
        assert r.created_at > 0

    def test_dependency_report_defaults(self):
        r = SLODependencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.unmapped_count == 0
        assert r.high_risk_count == 0
        assert r.by_status == {}
        assert r.by_type == {}
        assert r.by_risk == {}
        assert r.cascade_risk_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_mapping
# ---------------------------------------------------------------------------


class TestRecordMapping:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mapping(
            service="api-gateway",
            dependency_service="auth-svc",
            mapping_status=MappingStatus.MAPPED,
            dependency_type=DependencyType.HARD,
            risk_level=RiskLevel.HIGH,
            slo_target_pct=99.9,
            team="sre",
        )
        assert r.service == "api-gateway"
        assert r.dependency_service == "auth-svc"
        assert r.mapping_status == MappingStatus.MAPPED
        assert r.dependency_type == DependencyType.HARD
        assert r.risk_level == RiskLevel.HIGH
        assert r.slo_target_pct == 99.9
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(service=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_mapping
# ---------------------------------------------------------------------------


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(
            service="api-gateway",
            slo_target_pct=99.9,
        )
        result = eng.get_mapping(r.id)
        assert result is not None
        assert result.slo_target_pct == 99.9

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


# ---------------------------------------------------------------------------
# list_mappings
# ---------------------------------------------------------------------------


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(service="svc-1")
        eng.record_mapping(service="svc-2")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            mapping_status=MappingStatus.MAPPED,
        )
        eng.record_mapping(
            service="svc-2",
            mapping_status=MappingStatus.UNMAPPED,
        )
        results = eng.list_mappings(
            mapping_status=MappingStatus.MAPPED,
        )
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            dependency_type=DependencyType.HARD,
        )
        eng.record_mapping(
            service="svc-2",
            dependency_type=DependencyType.SOFT,
        )
        results = eng.list_mappings(
            dependency_type=DependencyType.HARD,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mapping(service="svc-1", team="sre")
        eng.record_mapping(service="svc-2", team="platform")
        results = eng.list_mappings(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(service=f"svc-{i}")
        assert len(eng.list_mappings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            service_pattern="api-*",
            mapping_status=MappingStatus.MAPPED,
            dependency_type=DependencyType.HARD,
            min_slo_pct=99.5,
            reason="Critical path",
        )
        assert r.service_pattern == "api-*"
        assert r.mapping_status == MappingStatus.MAPPED
        assert r.min_slo_pct == 99.5
        assert r.reason == "Critical path"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(service_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_mapping_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeMappingCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            mapping_status=MappingStatus.MAPPED,
        )
        eng.record_mapping(
            service="svc-2",
            mapping_status=MappingStatus.MAPPED,
        )
        result = eng.analyze_mapping_coverage()
        assert "mapped" in result
        assert result["mapped"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_mapping_coverage() == {}


# ---------------------------------------------------------------------------
# identify_unmapped_deps
# ---------------------------------------------------------------------------


class TestIdentifyUnmappedDeps:
    def test_detects_unmapped(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            mapping_status=MappingStatus.UNMAPPED,
        )
        eng.record_mapping(
            service="svc-2",
            mapping_status=MappingStatus.MAPPED,
        )
        results = eng.identify_unmapped_deps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unmapped_deps() == []


# ---------------------------------------------------------------------------
# rank_by_cascade_risk
# ---------------------------------------------------------------------------


class TestRankByCascadeRisk:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_mapping(
            service="svc-1",
            risk_level=RiskLevel.HIGH,
        )
        eng.record_mapping(
            service="svc-2",
            risk_level=RiskLevel.CRITICAL,
        )
        results = eng.rank_by_cascade_risk()
        assert len(results) == 2
        assert results[0]["service"] == "svc-1"
        assert results[0]["high_risk_dep_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cascade_risk() == []


# ---------------------------------------------------------------------------
# detect_mapping_trends
# ---------------------------------------------------------------------------


class TestDetectMappingTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [99.0, 99.0, 99.0, 99.0]:
            eng.record_mapping(service="svc-1", slo_target_pct=pct)
        result = eng.detect_mapping_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for pct in [90.0, 90.0, 99.0, 99.0]:
            eng.record_mapping(service="svc-1", slo_target_pct=pct)
        result = eng.detect_mapping_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_mapping_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            mapping_status=MappingStatus.UNMAPPED,
            risk_level=RiskLevel.CRITICAL,
        )
        report = eng.generate_report()
        assert isinstance(report, SLODependencyReport)
        assert report.total_records == 1
        assert report.unmapped_count == 1
        assert report.high_risk_count == 1
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
        eng.record_mapping(service="svc-1")
        eng.add_rule(service_pattern="pat-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            service="svc-1",
            mapping_status=MappingStatus.MAPPED,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "mapped" in stats["status_distribution"]

"""Tests for ServiceCatalogIntelligenceEngine."""

from __future__ import annotations

from shieldops.topology.service_catalog_intelligence_engine import (
    CatalogCompleteness,
    OwnershipStatus,
    ServiceCatalogIntelligenceEngine,
    ServiceTier,
)


def _engine(**kw) -> ServiceCatalogIntelligenceEngine:
    return ServiceCatalogIntelligenceEngine(**kw)


class TestEnums:
    def test_catalog_completeness_values(self):
        assert CatalogCompleteness.complete == "complete"
        assert CatalogCompleteness.partial == "partial"
        assert CatalogCompleteness.minimal == "minimal"
        assert CatalogCompleteness.missing == "missing"
        assert CatalogCompleteness.unknown == "unknown"

    def test_ownership_status_values(self):
        assert OwnershipStatus.owned == "owned"
        assert OwnershipStatus.shared == "shared"
        assert OwnershipStatus.orphaned == "orphaned"
        assert OwnershipStatus.disputed == "disputed"
        assert OwnershipStatus.transitioning == "transitioning"

    def test_service_tier_values(self):
        assert ServiceTier.tier_0_critical == "tier_0_critical"
        assert ServiceTier.tier_1_important == "tier_1_important"
        assert ServiceTier.unclassified == "unclassified"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            service_name="auth-svc",
            tier=ServiceTier.tier_0_critical,
        )
        assert r.service_name == "auth-svc"
        assert r.tier == ServiceTier.tier_0_critical

    def test_eviction_at_max(self):
        eng = _engine(max_records=20)
        for i in range(25):
            eng.record_item(service_name=f"svc-{i}")
        stats = eng.get_stats()
        assert stats["total_records"] < 25


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.record_item(
            service_name="api",
            doc_coverage_pct=50.0,
        )
        result = eng.process(r.id)
        assert isinstance(result.health_score, float)

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result.record_id == ""


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        r = eng.record_item(service_name="svc")
        eng.process(r.id)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.record_item(service_name="x")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(service_name="x")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestScoreCatalogHealth:
    def test_returns_float(self):
        eng = _engine()
        eng.record_item(
            service_name="x",
            completeness=CatalogCompleteness.complete,
        )
        result = eng.score_catalog_health()
        assert isinstance(result, float)


class TestIdentifyOrphans:
    def test_returns_list(self):
        eng = _engine()
        eng.record_item(
            service_name="orphan",
            ownership_status=OwnershipStatus.orphaned,
        )
        result = eng.identify_orphans()
        assert isinstance(result, list)
        assert len(result) == 1


class TestComputeDocCoverage:
    def test_returns_dict(self):
        eng = _engine()
        eng.record_item(
            service_name="x",
            team="platform",
            doc_coverage_pct=75.0,
        )
        result = eng.compute_documentation_coverage()
        assert isinstance(result, dict)

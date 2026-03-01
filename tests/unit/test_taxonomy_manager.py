"""Tests for shieldops.knowledge.taxonomy_manager — TaxonomyManager."""

from __future__ import annotations

from shieldops.knowledge.taxonomy_manager import (
    TaxonomyLevel,
    TaxonomyManager,
    TaxonomyMapping,
    TaxonomyQuality,
    TaxonomyRecord,
    TaxonomyReport,
    TaxonomyStatus,
)


def _engine(**kw) -> TaxonomyManager:
    return TaxonomyManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_domain(self):
        assert TaxonomyLevel.DOMAIN == "domain"

    def test_level_category(self):
        assert TaxonomyLevel.CATEGORY == "category"

    def test_level_subcategory(self):
        assert TaxonomyLevel.SUBCATEGORY == "subcategory"

    def test_level_topic(self):
        assert TaxonomyLevel.TOPIC == "topic"

    def test_level_tag(self):
        assert TaxonomyLevel.TAG == "tag"

    def test_status_active(self):
        assert TaxonomyStatus.ACTIVE == "active"

    def test_status_draft(self):
        assert TaxonomyStatus.DRAFT == "draft"

    def test_status_deprecated(self):
        assert TaxonomyStatus.DEPRECATED == "deprecated"

    def test_status_archived(self):
        assert TaxonomyStatus.ARCHIVED == "archived"

    def test_status_pending_review(self):
        assert TaxonomyStatus.PENDING_REVIEW == "pending_review"

    def test_quality_excellent(self):
        assert TaxonomyQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert TaxonomyQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert TaxonomyQuality.ADEQUATE == "adequate"

    def test_quality_needs_improvement(self):
        assert TaxonomyQuality.NEEDS_IMPROVEMENT == "needs_improvement"

    def test_quality_poor(self):
        assert TaxonomyQuality.POOR == "poor"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_taxonomy_record_defaults(self):
        r = TaxonomyRecord()
        assert r.id
        assert r.taxonomy_id == ""
        assert r.taxonomy_level == TaxonomyLevel.DOMAIN
        assert r.taxonomy_status == TaxonomyStatus.DRAFT
        assert r.taxonomy_quality == TaxonomyQuality.ADEQUATE
        assert r.completeness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_taxonomy_mapping_defaults(self):
        m = TaxonomyMapping()
        assert m.id
        assert m.taxonomy_id == ""
        assert m.taxonomy_level == TaxonomyLevel.DOMAIN
        assert m.mapping_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_taxonomy_report_defaults(self):
        r = TaxonomyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_mappings == 0
        assert r.poor_taxonomies == 0
        assert r.avg_completeness_score == 0.0
        assert r.by_level == {}
        assert r.by_status == {}
        assert r.by_quality == {}
        assert r.top_incomplete == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_taxonomy
# ---------------------------------------------------------------------------


class TestRecordTaxonomy:
    def test_basic(self):
        eng = _engine()
        r = eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_level=TaxonomyLevel.CATEGORY,
            taxonomy_status=TaxonomyStatus.ACTIVE,
            taxonomy_quality=TaxonomyQuality.GOOD,
            completeness_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.taxonomy_id == "TAX-001"
        assert r.taxonomy_level == TaxonomyLevel.CATEGORY
        assert r.taxonomy_status == TaxonomyStatus.ACTIVE
        assert r.taxonomy_quality == TaxonomyQuality.GOOD
        assert r.completeness_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_taxonomy(taxonomy_id=f"TAX-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_taxonomy
# ---------------------------------------------------------------------------


class TestGetTaxonomy:
    def test_found(self):
        eng = _engine()
        r = eng.record_taxonomy(
            taxonomy_id="TAX-001",
            completeness_score=90.0,
        )
        result = eng.get_taxonomy(r.id)
        assert result is not None
        assert result.completeness_score == 90.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_taxonomy("nonexistent") is None


# ---------------------------------------------------------------------------
# list_taxonomies
# ---------------------------------------------------------------------------


class TestListTaxonomies:
    def test_list_all(self):
        eng = _engine()
        eng.record_taxonomy(taxonomy_id="TAX-001")
        eng.record_taxonomy(taxonomy_id="TAX-002")
        assert len(eng.list_taxonomies()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_level=TaxonomyLevel.DOMAIN,
        )
        eng.record_taxonomy(
            taxonomy_id="TAX-002",
            taxonomy_level=TaxonomyLevel.TOPIC,
        )
        results = eng.list_taxonomies(level=TaxonomyLevel.DOMAIN)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_status=TaxonomyStatus.ACTIVE,
        )
        eng.record_taxonomy(
            taxonomy_id="TAX-002",
            taxonomy_status=TaxonomyStatus.DEPRECATED,
        )
        results = eng.list_taxonomies(status=TaxonomyStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_taxonomy(taxonomy_id="TAX-001", service="api-gateway")
        eng.record_taxonomy(taxonomy_id="TAX-002", service="auth-svc")
        results = eng.list_taxonomies(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_taxonomy(taxonomy_id="TAX-001", team="sre")
        eng.record_taxonomy(taxonomy_id="TAX-002", team="platform")
        results = eng.list_taxonomies(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_taxonomy(taxonomy_id=f"TAX-{i}")
        assert len(eng.list_taxonomies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_mapping
# ---------------------------------------------------------------------------


class TestAddMapping:
    def test_basic(self):
        eng = _engine()
        m = eng.add_mapping(
            taxonomy_id="TAX-001",
            taxonomy_level=TaxonomyLevel.CATEGORY,
            mapping_score=85.0,
            threshold=70.0,
            breached=False,
            description="Well-categorized",
        )
        assert m.taxonomy_id == "TAX-001"
        assert m.taxonomy_level == TaxonomyLevel.CATEGORY
        assert m.mapping_score == 85.0
        assert m.threshold == 70.0
        assert m.breached is False
        assert m.description == "Well-categorized"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_mapping(taxonomy_id=f"TAX-{i}")
        assert len(eng._mappings) == 2


# ---------------------------------------------------------------------------
# analyze_taxonomy_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeTaxonomyCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_level=TaxonomyLevel.DOMAIN,
            completeness_score=80.0,
        )
        eng.record_taxonomy(
            taxonomy_id="TAX-002",
            taxonomy_level=TaxonomyLevel.DOMAIN,
            completeness_score=60.0,
        )
        result = eng.analyze_taxonomy_coverage()
        assert "domain" in result
        assert result["domain"]["count"] == 2
        assert result["domain"]["avg_completeness"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_taxonomy_coverage() == {}


# ---------------------------------------------------------------------------
# identify_poor_taxonomies
# ---------------------------------------------------------------------------


class TestIdentifyPoorTaxonomies:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_quality=TaxonomyQuality.POOR,
        )
        eng.record_taxonomy(
            taxonomy_id="TAX-002",
            taxonomy_quality=TaxonomyQuality.EXCELLENT,
        )
        results = eng.identify_poor_taxonomies()
        assert len(results) == 1
        assert results[0]["taxonomy_id"] == "TAX-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_taxonomies() == []


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankByCompleteness:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            service="api-gateway",
            completeness_score=90.0,
        )
        eng.record_taxonomy(
            taxonomy_id="TAX-002",
            service="auth-svc",
            completeness_score=60.0,
        )
        results = eng.rank_by_completeness()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_completeness"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_taxonomy_trends
# ---------------------------------------------------------------------------


class TestDetectTaxonomyTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.add_mapping(taxonomy_id="TAX-001", mapping_score=score)
        result = eng.detect_taxonomy_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [30.0, 30.0, 80.0, 80.0]:
            eng.add_mapping(taxonomy_id="TAX-001", mapping_score=score)
        result = eng.detect_taxonomy_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_taxonomy_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_level=TaxonomyLevel.DOMAIN,
            taxonomy_quality=TaxonomyQuality.POOR,
            completeness_score=30.0,
            service="api-gateway",
        )
        report = eng.generate_report()
        assert isinstance(report, TaxonomyReport)
        assert report.total_records == 1
        assert report.poor_taxonomies == 1
        assert len(report.top_incomplete) == 1
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
        eng.record_taxonomy(taxonomy_id="TAX-001")
        eng.add_mapping(taxonomy_id="TAX-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._mappings) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_mappings"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_taxonomy(
            taxonomy_id="TAX-001",
            taxonomy_level=TaxonomyLevel.DOMAIN,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "domain" in stats["level_distribution"]

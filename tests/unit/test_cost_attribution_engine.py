"""Tests for shieldops.billing.cost_attribution_engine — CostAttributionEngine."""

from __future__ import annotations

from shieldops.billing.cost_attribution_engine import (
    AttributionAccuracy,
    AttributionDetail,
    AttributionMethod,
    AttributionRecord,
    CostAttributionEngine,
    CostAttributionReport,
    CostCategory,
)


def _engine(**kw) -> CostAttributionEngine:
    return CostAttributionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_method_direct(self):
        assert AttributionMethod.DIRECT == "direct"

    def test_method_proportional(self):
        assert AttributionMethod.PROPORTIONAL == "proportional"

    def test_method_equal_split(self):
        assert AttributionMethod.EQUAL_SPLIT == "equal_split"

    def test_method_usage_based(self):
        assert AttributionMethod.USAGE_BASED == "usage_based"

    def test_method_custom(self):
        assert AttributionMethod.CUSTOM == "custom"

    def test_category_infrastructure(self):
        assert CostCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_platform(self):
        assert CostCategory.PLATFORM == "platform"

    def test_category_tooling(self):
        assert CostCategory.TOOLING == "tooling"

    def test_category_support(self):
        assert CostCategory.SUPPORT == "support"

    def test_category_overhead(self):
        assert CostCategory.OVERHEAD == "overhead"

    def test_accuracy_verified(self):
        assert AttributionAccuracy.VERIFIED == "verified"

    def test_accuracy_estimated(self):
        assert AttributionAccuracy.ESTIMATED == "estimated"

    def test_accuracy_projected(self):
        assert AttributionAccuracy.PROJECTED == "projected"

    def test_accuracy_approximate(self):
        assert AttributionAccuracy.APPROXIMATE == "approximate"

    def test_accuracy_unknown(self):
        assert AttributionAccuracy.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_attribution_record_defaults(self):
        r = AttributionRecord()
        assert r.id
        assert r.attribution_id == ""
        assert r.attribution_method == AttributionMethod.DIRECT
        assert r.cost_category == CostCategory.INFRASTRUCTURE
        assert r.attribution_accuracy == AttributionAccuracy.UNKNOWN
        assert r.cost_amount == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_attribution_detail_defaults(self):
        m = AttributionDetail()
        assert m.id
        assert m.attribution_id == ""
        assert m.attribution_method == AttributionMethod.DIRECT
        assert m.detail_amount == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_cost_attribution_report_defaults(self):
        r = CostAttributionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_details == 0
        assert r.disputed_attributions == 0
        assert r.avg_cost_amount == 0.0
        assert r.by_method == {}
        assert r.by_category == {}
        assert r.by_accuracy == {}
        assert r.top_attributed == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_attribution
# ---------------------------------------------------------------------------


class TestRecordAttribution:
    def test_basic(self):
        eng = _engine()
        r = eng.record_attribution(
            attribution_id="ATT-001",
            attribution_method=AttributionMethod.DIRECT,
            cost_category=CostCategory.INFRASTRUCTURE,
            attribution_accuracy=AttributionAccuracy.VERIFIED,
            cost_amount=1500.0,
            service="api-gateway",
            team="sre",
        )
        assert r.attribution_id == "ATT-001"
        assert r.attribution_method == AttributionMethod.DIRECT
        assert r.cost_category == CostCategory.INFRASTRUCTURE
        assert r.attribution_accuracy == AttributionAccuracy.VERIFIED
        assert r.cost_amount == 1500.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_attribution(attribution_id=f"ATT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_attribution
# ---------------------------------------------------------------------------


class TestGetAttribution:
    def test_found(self):
        eng = _engine()
        r = eng.record_attribution(
            attribution_id="ATT-001",
            attribution_accuracy=AttributionAccuracy.VERIFIED,
        )
        result = eng.get_attribution(r.id)
        assert result is not None
        assert result.attribution_accuracy == AttributionAccuracy.VERIFIED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_attribution("nonexistent") is None


# ---------------------------------------------------------------------------
# list_attributions
# ---------------------------------------------------------------------------


class TestListAttributions:
    def test_list_all(self):
        eng = _engine()
        eng.record_attribution(attribution_id="ATT-001")
        eng.record_attribution(attribution_id="ATT-002")
        assert len(eng.list_attributions()) == 2

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            attribution_method=AttributionMethod.DIRECT,
        )
        eng.record_attribution(
            attribution_id="ATT-002",
            attribution_method=AttributionMethod.PROPORTIONAL,
        )
        results = eng.list_attributions(
            method=AttributionMethod.DIRECT,
        )
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            cost_category=CostCategory.INFRASTRUCTURE,
        )
        eng.record_attribution(
            attribution_id="ATT-002",
            cost_category=CostCategory.PLATFORM,
        )
        results = eng.list_attributions(
            category=CostCategory.INFRASTRUCTURE,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_attribution(attribution_id="ATT-001", service="api-gateway")
        eng.record_attribution(attribution_id="ATT-002", service="auth-svc")
        results = eng.list_attributions(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_attribution(attribution_id="ATT-001", team="sre")
        eng.record_attribution(attribution_id="ATT-002", team="platform")
        results = eng.list_attributions(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_attribution(attribution_id=f"ATT-{i}")
        assert len(eng.list_attributions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_detail
# ---------------------------------------------------------------------------


class TestAddDetail:
    def test_basic(self):
        eng = _engine()
        m = eng.add_detail(
            attribution_id="ATT-001",
            attribution_method=AttributionMethod.PROPORTIONAL,
            detail_amount=500.0,
            threshold=1000.0,
            breached=False,
            description="Shared cost portion",
        )
        assert m.attribution_id == "ATT-001"
        assert m.attribution_method == AttributionMethod.PROPORTIONAL
        assert m.detail_amount == 500.0
        assert m.threshold == 1000.0
        assert m.breached is False
        assert m.description == "Shared cost portion"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_detail(attribution_id=f"ATT-{i}")
        assert len(eng._details) == 2


# ---------------------------------------------------------------------------
# analyze_attribution_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeAttributionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            attribution_method=AttributionMethod.DIRECT,
            cost_amount=100.0,
        )
        eng.record_attribution(
            attribution_id="ATT-002",
            attribution_method=AttributionMethod.DIRECT,
            cost_amount=200.0,
        )
        result = eng.analyze_attribution_distribution()
        assert "direct" in result
        assert result["direct"]["count"] == 2
        assert result["direct"]["avg_cost_amount"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_attribution_distribution() == {}


# ---------------------------------------------------------------------------
# identify_disputed_attributions
# ---------------------------------------------------------------------------


class TestIdentifyDisputedAttributions:
    def test_detects_unknown(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            attribution_accuracy=AttributionAccuracy.UNKNOWN,
        )
        eng.record_attribution(
            attribution_id="ATT-002",
            attribution_accuracy=AttributionAccuracy.VERIFIED,
        )
        results = eng.identify_disputed_attributions()
        assert len(results) == 1
        assert results[0]["attribution_id"] == "ATT-001"

    def test_detects_approximate(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            attribution_accuracy=AttributionAccuracy.APPROXIMATE,
        )
        results = eng.identify_disputed_attributions()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_disputed_attributions() == []


# ---------------------------------------------------------------------------
# rank_by_cost_amount
# ---------------------------------------------------------------------------


class TestRankByCostAmount:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            service="api-gateway",
            cost_amount=5000.0,
        )
        eng.record_attribution(
            attribution_id="ATT-002",
            service="auth-svc",
            cost_amount=1000.0,
        )
        results = eng.rank_by_cost_amount()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["total_cost"] == 5000.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_amount() == []


# ---------------------------------------------------------------------------
# detect_attribution_trends
# ---------------------------------------------------------------------------


class TestDetectAttributionTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_detail(attribution_id="ATT-1", detail_amount=val)
        result = eng.detect_attribution_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [10.0, 10.0, 50.0, 50.0]:
            eng.add_detail(attribution_id="ATT-1", detail_amount=val)
        result = eng.detect_attribution_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_attribution_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            attribution_method=AttributionMethod.DIRECT,
            cost_category=CostCategory.INFRASTRUCTURE,
            attribution_accuracy=AttributionAccuracy.UNKNOWN,
            cost_amount=2500.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CostAttributionReport)
        assert report.total_records == 1
        assert report.disputed_attributions == 1
        assert len(report.top_attributed) >= 1
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
        eng.record_attribution(attribution_id="ATT-001")
        eng.add_detail(attribution_id="ATT-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._details) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_details"] == 0
        assert stats["method_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_attribution(
            attribution_id="ATT-001",
            attribution_method=AttributionMethod.DIRECT,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "direct" in stats["method_distribution"]

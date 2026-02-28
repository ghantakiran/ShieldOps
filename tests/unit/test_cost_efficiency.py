"""Tests for shieldops.billing.cost_efficiency — CostEfficiencyScorer."""

from __future__ import annotations

from shieldops.billing.cost_efficiency import (
    CostEfficiencyReport,
    CostEfficiencyScorer,
    EfficiencyCategory,
    EfficiencyGrade,
    EfficiencyMetric,
    EfficiencyRecord,
    OptimizationPotential,
)


def _engine(**kw) -> CostEfficiencyScorer:
    return CostEfficiencyScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EfficiencyCategory (5)
    def test_category_compute(self):
        assert EfficiencyCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert EfficiencyCategory.STORAGE == "storage"

    def test_category_network(self):
        assert EfficiencyCategory.NETWORK == "network"

    def test_category_database(self):
        assert EfficiencyCategory.DATABASE == "database"

    def test_category_services(self):
        assert EfficiencyCategory.SERVICES == "services"

    # EfficiencyGrade (5)
    def test_grade_excellent(self):
        assert EfficiencyGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert EfficiencyGrade.GOOD == "good"

    def test_grade_adequate(self):
        assert EfficiencyGrade.ADEQUATE == "adequate"

    def test_grade_poor(self):
        assert EfficiencyGrade.POOR == "poor"

    def test_grade_wasteful(self):
        assert EfficiencyGrade.WASTEFUL == "wasteful"

    # OptimizationPotential (5)
    def test_potential_high(self):
        assert OptimizationPotential.HIGH == "high"

    def test_potential_moderate(self):
        assert OptimizationPotential.MODERATE == "moderate"

    def test_potential_low(self):
        assert OptimizationPotential.LOW == "low"

    def test_potential_minimal(self):
        assert OptimizationPotential.MINIMAL == "minimal"

    def test_potential_none(self):
        assert OptimizationPotential.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_efficiency_record_defaults(self):
        r = EfficiencyRecord()
        assert r.id
        assert r.service_name == ""
        assert r.category == EfficiencyCategory.COMPUTE
        assert r.grade == EfficiencyGrade.ADEQUATE
        assert r.potential == OptimizationPotential.MODERATE
        assert r.efficiency_pct == 0.0
        assert r.monthly_cost == 0.0
        assert r.wasted_spend == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_efficiency_metric_defaults(self):
        m = EfficiencyMetric()
        assert m.id
        assert m.service_name == ""
        assert m.category == EfficiencyCategory.COMPUTE
        assert m.metric_name == ""
        assert m.value == 0.0
        assert m.unit == ""
        assert m.created_at > 0

    def test_cost_efficiency_report_defaults(self):
        r = CostEfficiencyReport()
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.avg_efficiency_pct == 0.0
        assert r.by_category == {}
        assert r.by_grade == {}
        assert r.wasteful_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_efficiency
# ---------------------------------------------------------------------------


class TestRecordEfficiency:
    def test_basic(self):
        eng = _engine()
        r = eng.record_efficiency(
            service_name="api",
            category=EfficiencyCategory.COMPUTE,
            efficiency_pct=85.0,
            monthly_cost=500.0,
        )
        assert r.service_name == "api"
        assert r.efficiency_pct == 85.0
        assert r.grade == EfficiencyGrade.GOOD

    def test_auto_grade_excellent(self):
        eng = _engine()
        r = eng.record_efficiency("api", efficiency_pct=95.0)
        assert r.grade == EfficiencyGrade.EXCELLENT

    def test_auto_grade_wasteful(self):
        eng = _engine()
        r = eng.record_efficiency("api", efficiency_pct=20.0)
        assert r.grade == EfficiencyGrade.WASTEFUL

    def test_explicit_grade_overrides(self):
        eng = _engine()
        r = eng.record_efficiency("api", efficiency_pct=95.0, grade=EfficiencyGrade.POOR)
        assert r.grade == EfficiencyGrade.POOR

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_efficiency(f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_efficiency
# ---------------------------------------------------------------------------


class TestGetEfficiency:
    def test_found(self):
        eng = _engine()
        r = eng.record_efficiency("api")
        assert eng.get_efficiency(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_efficiency("nonexistent") is None


# ---------------------------------------------------------------------------
# list_efficiencies
# ---------------------------------------------------------------------------


class TestListEfficiencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_efficiency("api")
        eng.record_efficiency("db")
        assert len(eng.list_efficiencies()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_efficiency("api")
        eng.record_efficiency("db")
        results = eng.list_efficiencies(service_name="api")
        assert len(results) == 1
        assert results[0].service_name == "api"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_efficiency("api", category=EfficiencyCategory.COMPUTE)
        eng.record_efficiency("db", category=EfficiencyCategory.DATABASE)
        results = eng.list_efficiencies(category=EfficiencyCategory.COMPUTE)
        assert len(results) == 1
        assert results[0].category == EfficiencyCategory.COMPUTE


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            service_name="api",
            category=EfficiencyCategory.COMPUTE,
            metric_name="cpu_utilization",
            value=45.0,
            unit="percent",
        )
        assert m.service_name == "api"
        assert m.metric_name == "cpu_utilization"
        assert m.value == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_metric(service_name=f"svc-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_efficiency_by_service
# ---------------------------------------------------------------------------


class TestAnalyzeEfficiencyByService:
    def test_with_data(self):
        eng = _engine(min_efficiency_pct=70.0)
        eng.record_efficiency("api", efficiency_pct=80.0, monthly_cost=500.0, wasted_spend=100.0)
        eng.record_efficiency("api", efficiency_pct=60.0, monthly_cost=300.0, wasted_spend=50.0)
        result = eng.analyze_efficiency_by_service("api")
        assert result["service_name"] == "api"
        assert result["total_resources"] == 2
        assert result["avg_efficiency_pct"] == 70.0
        assert result["total_monthly_cost"] == 800.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_efficiency_by_service("ghost")
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_wasteful_resources
# ---------------------------------------------------------------------------


class TestIdentifyWastefulResources:
    def test_with_wasteful(self):
        eng = _engine()
        eng.record_efficiency("api", efficiency_pct=20.0, wasted_spend=1000.0)
        eng.record_efficiency("db", efficiency_pct=95.0, wasted_spend=0.0)
        results = eng.identify_wasteful_resources()
        assert len(results) == 1
        assert results[0]["service_name"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_wasteful_resources() == []


# ---------------------------------------------------------------------------
# rank_by_efficiency_score
# ---------------------------------------------------------------------------


class TestRankByEfficiencyScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_efficiency("api", efficiency_pct=90.0)
        eng.record_efficiency("db", efficiency_pct=30.0)
        results = eng.rank_by_efficiency_score()
        assert results[0]["efficiency_pct"] == 30.0
        assert results[1]["efficiency_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_efficiency_score() == []


# ---------------------------------------------------------------------------
# detect_efficiency_trends
# ---------------------------------------------------------------------------


class TestDetectEfficiencyTrends:
    def test_declining(self):
        eng = _engine()
        eng.record_efficiency("api", efficiency_pct=90.0)
        eng.record_efficiency("api", efficiency_pct=60.0)
        trends = eng.detect_efficiency_trends()
        assert len(trends) == 1
        assert trends[0]["declining"] is True
        assert trends[0]["efficiency_delta"] == -30.0

    def test_single_record_no_trend(self):
        eng = _engine()
        eng.record_efficiency("api", efficiency_pct=80.0)
        trends = eng.detect_efficiency_trends()
        assert len(trends) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_efficiency_pct=70.0)
        eng.record_efficiency("api", efficiency_pct=20.0, wasted_spend=500.0)
        eng.add_metric("api", metric_name="cpu")
        report = eng.generate_report()
        assert isinstance(report, CostEfficiencyReport)
        assert report.total_records == 1
        assert report.total_metrics == 1
        assert report.wasteful_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "meets optimization targets" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_efficiency("api")
        eng.add_metric("api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["grade_distribution"] == {}
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_efficiency("api", efficiency_pct=95.0)
        eng.record_efficiency("db", efficiency_pct=20.0)
        eng.add_metric("api")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_metrics"] == 1
        assert stats["unique_services"] == 2
        assert "excellent" in stats["grade_distribution"]

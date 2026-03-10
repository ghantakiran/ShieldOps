"""Tests for OperationalComplexityScorer."""

from __future__ import annotations

from shieldops.analytics.operational_complexity_scorer import (
    ComplexityDimension,
    ComplexityDriver,
    OperationalComplexityScorer,
    RiskImpact,
)


def _engine(**kw) -> OperationalComplexityScorer:
    return OperationalComplexityScorer(**kw)


class TestEnums:
    def test_complexity_dimension_values(self):
        assert ComplexityDimension.ARCHITECTURAL == "architectural"
        assert ComplexityDimension.OPERATIONAL == "operational"
        assert ComplexityDimension.ORGANIZATIONAL == "organizational"
        assert ComplexityDimension.TECHNICAL == "technical"

    def test_complexity_driver_values(self):
        assert ComplexityDriver.DEPENDENCIES == "dependencies"
        assert ComplexityDriver.SCALE == "scale"
        assert ComplexityDriver.HETEROGENEITY == "heterogeneity"
        assert ComplexityDriver.CHANGE_RATE == "change_rate"

    def test_risk_impact_values(self):
        assert RiskImpact.CRITICAL == "critical"
        assert RiskImpact.HIGH == "high"
        assert RiskImpact.MODERATE == "moderate"
        assert RiskImpact.LOW == "low"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="comp-001",
            complexity_dimension=ComplexityDimension.TECHNICAL,
            complexity_driver=ComplexityDriver.SCALE,
            risk_impact=RiskImpact.HIGH,
            score=70.0,
            service="api",
            team="platform",
        )
        assert r.name == "comp-001"
        assert r.complexity_dimension == ComplexityDimension.TECHNICAL
        assert r.score == 70.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

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
        eng.add_record(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestComputeComplexityScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            name="a",
            risk_impact=RiskImpact.CRITICAL,
            score=80.0,
        )
        result = eng.compute_complexity_score()
        assert result["overall_complexity"] > 0
        assert result["total_records"] == 1

    def test_empty(self):
        eng = _engine()
        result = eng.compute_complexity_score()
        assert result["overall_complexity"] == 0.0


class TestIdentifyComplexityHotspots:
    def test_with_data(self):
        eng = _engine(threshold=50.0)
        eng.add_record(name="a", service="api", score=80.0)
        eng.add_record(name="b", service="db", score=30.0)
        results = eng.identify_complexity_hotspots()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["is_hotspot"] is True

    def test_empty(self):
        eng = _engine()
        assert eng.identify_complexity_hotspots() == []


class TestRecommendSimplification:
    def test_with_high_complexity(self):
        eng = _engine(threshold=50.0)
        eng.add_record(
            name="a",
            complexity_driver=ComplexityDriver.DEPENDENCIES,
            score=80.0,
        )
        results = eng.recommend_simplification()
        assert len(results) == 1
        assert results[0]["driver"] == "dependencies"

    def test_no_recs_below_threshold(self):
        eng = _engine(threshold=90.0)
        eng.add_record(
            name="a",
            complexity_driver=ComplexityDriver.SCALE,
            score=30.0,
        )
        results = eng.recommend_simplification()
        assert len(results) == 0

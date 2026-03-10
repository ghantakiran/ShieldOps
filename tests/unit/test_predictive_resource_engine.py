"""Tests for PredictiveResourceEngine."""

from __future__ import annotations

from shieldops.billing.predictive_resource_engine import (
    PredictionConfidence,
    PredictiveResourceEngine,
    ResourceDemandTrend,
    SizingRecommendation,
)


def _engine(**kw) -> PredictiveResourceEngine:
    return PredictiveResourceEngine(**kw)


class TestEnums:
    def test_resource_demand_trend(self):
        assert ResourceDemandTrend.GROWING == "growing"

    def test_sizing_recommendation(self):
        assert SizingRecommendation.DOWNSIZE == "downsize"

    def test_prediction_confidence(self):
        assert PredictionConfidence.HIGH == "high"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(service="api")
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(service=f"svc-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(service="api")
        result = eng.process("api")
        assert isinstance(result, dict)
        assert result["service"] == "api"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestPredictDemand:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            service="api",
            predicted_usage_pct=0.75,
        )
        result = eng.predict_demand("api")
        assert isinstance(result, dict)


class TestRecommendSizing:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            service="api",
            resource_type="cpu",
        )
        result = eng.recommend_sizing("api")
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0

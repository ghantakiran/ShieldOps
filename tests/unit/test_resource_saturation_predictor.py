"""Tests for ResourceSaturationPredictor."""

from __future__ import annotations

from shieldops.operations.resource_saturation_predictor import (
    PredictionConfidence,
    ResourceCategory,
    ResourceSaturationPredictor,
    SaturationLevel,
)


def _engine(**kw) -> ResourceSaturationPredictor:
    return ResourceSaturationPredictor(**kw)


class TestEnums:
    def test_saturation_level_values(self):
        for v in SaturationLevel:
            assert isinstance(v.value, str)

    def test_resource_category_values(self):
        for v in ResourceCategory:
            assert isinstance(v.value, str)

    def test_prediction_confidence_values(self):
        for v in PredictionConfidence:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(resource_id="r1")
        assert r.resource_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(resource_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.record_item(
            resource_id="r1",
            saturation_level=SaturationLevel.CRITICAL,
            resource_category=ResourceCategory.MEMORY,
            current_usage_pct=95.0,
            hours_to_saturation=2.0,
        )
        assert r.current_usage_pct == 95.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(resource_id="r1", current_usage_pct=80.0)
        a = eng.process(r.id)
        assert hasattr(a, "resource_id")
        assert a.resource_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_approaching_detected(self):
        eng = _engine()
        r = eng.record_item(
            resource_id="r1",
            saturation_level=SaturationLevel.CRITICAL,
        )
        a = eng.process(r.id)
        assert a.approaching is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeSaturationTimeline:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(resource_id="r1", hours_to_saturation=5.0)
        result = eng.compute_saturation_timeline()
        assert len(result) == 1
        assert result[0]["resource_id"] == "r1"

    def test_empty(self):
        assert _engine().compute_saturation_timeline() == []


class TestDetectApproachingSaturation:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            saturation_level=SaturationLevel.DANGER,
            current_usage_pct=90.0,
            hours_to_saturation=3.0,
        )
        result = eng.detect_approaching_saturation()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_approaching_saturation() == []


class TestRankResourcesBySaturationUrgency:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(resource_id="r1", current_usage_pct=80.0)
        eng.record_item(resource_id="r2", current_usage_pct=95.0)
        result = eng.rank_resources_by_saturation_urgency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_resources_by_saturation_urgency() == []

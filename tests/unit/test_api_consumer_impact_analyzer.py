"""Tests for ApiConsumerImpactAnalyzer."""

from __future__ import annotations

from shieldops.topology.api_consumer_impact_analyzer import (
    ApiConsumerImpactAnalyzer,
    ChangeType,
    ConsumerTier,
    ImpactLevel,
)


def _engine(**kw) -> ApiConsumerImpactAnalyzer:
    return ApiConsumerImpactAnalyzer(**kw)


class TestEnums:
    def test_impact_level_values(self):
        for v in ImpactLevel:
            assert isinstance(v.value, str)

    def test_consumer_tier_values(self):
        for v in ConsumerTier:
            assert isinstance(v.value, str)

    def test_change_type_values(self):
        for v in ChangeType:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(consumer_id="c-1")
        assert r.consumer_id == "c-1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(consumer_id=f"c-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            api_name="users-api",
            consumer_id="c-1",
            impact_level=ImpactLevel.BREAKING,
            affected_endpoints=5,
        )
        assert r.affected_endpoints == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            consumer_id="c-1",
            affected_endpoints=3,
        )
        a = eng.process(r.id)
        assert a.consumer_id == "c-1"

    def test_breaking(self):
        eng = _engine()
        r = eng.record_item(
            impact_level=ImpactLevel.BREAKING,
        )
        a = eng.process(r.id)
        assert a.is_breaking is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(consumer_id="c-1")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_breaking_consumers(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            impact_level=ImpactLevel.BREAKING,
        )
        rpt = eng.generate_report()
        assert len(rpt.breaking_consumers) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(consumer_id="c-1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(consumer_id="c-1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapConsumerDependencies:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            api_name="users-api",
            consumer_id="c-1",
        )
        eng.record_item(
            api_name="users-api",
            consumer_id="c-2",
        )
        result = eng.map_consumer_dependencies()
        assert len(result) == 1
        assert result[0]["consumer_count"] == 2

    def test_empty(self):
        assert _engine().map_consumer_dependencies() == []


class TestSimulateChangeImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            api_name="users-api",
            consumer_id="c-1",
            impact_level=ImpactLevel.BREAKING,
            affected_endpoints=5,
        )
        result = eng.simulate_change_impact()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().simulate_change_impact() == []


class TestPrioritizeConsumerNotification:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            consumer_id="c-1",
            consumer_tier=ConsumerTier.PREMIUM,
        )
        result = eng.prioritize_consumer_notification()
        assert len(result) == 1
        assert result[0]["priority"] == 4

    def test_empty(self):
        assert _engine().prioritize_consumer_notification() == []

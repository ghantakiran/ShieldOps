"""Tests for MessageOrderingGuaranteeTracker."""

from __future__ import annotations

from shieldops.observability.message_ordering_guarantee_tracker import (
    ConsistencyLevel,
    MessageOrderingGuaranteeTracker,
    OrderingGuarantee,
    ViolationType,
)


def _engine(**kw) -> MessageOrderingGuaranteeTracker:
    return MessageOrderingGuaranteeTracker(**kw)


class TestEnums:
    def test_ordering_guarantee_values(self):
        for v in OrderingGuarantee:
            assert isinstance(v.value, str)

    def test_violation_type_values(self):
        for v in ViolationType:
            assert isinstance(v.value, str)

    def test_consistency_level_values(self):
        for v in ConsistencyLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(consumer_id="c1")
        assert r.consumer_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(consumer_id=f"c-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.ordering_guarantee == (OrderingGuarantee.PARTITION)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            consumer_id="c1",
            violation_count=5,
            message_count=100,
        )
        a = eng.process(r.id)
        assert hasattr(a, "consumer_id")
        assert a.consumer_id == "c1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(consumer_id="c1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_risky_consumers(self):
        eng = _engine()
        eng.add_record(
            consumer_id="c1",
            consistency_level=ConsistencyLevel.LOW,
        )
        rpt = eng.generate_report()
        assert len(rpt.risky_consumers) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(consumer_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(consumer_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDetectOrderingViolations:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_id="c1",
            violation_count=10,
            message_count=100,
        )
        result = eng.detect_ordering_violations()
        assert len(result) == 1
        assert result[0]["violations"] == 10

    def test_no_violations(self):
        eng = _engine()
        eng.add_record(
            consumer_id="c1",
            violation_count=0,
            message_count=100,
        )
        assert eng.detect_ordering_violations() == []


class TestComputeOrderingConsistencyScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_id="c1",
            violation_count=5,
            message_count=100,
        )
        result = eng.compute_ordering_consistency_score()
        assert len(result) == 1
        assert result[0]["consistency_score"] == 95.0

    def test_empty(self):
        r = _engine().compute_ordering_consistency_score()
        assert r == []


class TestRankConsumersByOrderingRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            consumer_id="c1",
            violation_count=20,
            message_count=100,
        )
        eng.add_record(
            consumer_id="c2",
            violation_count=1,
            message_count=100,
        )
        result = eng.rank_consumers_by_ordering_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_consumers_by_ordering_risk()
        assert r == []

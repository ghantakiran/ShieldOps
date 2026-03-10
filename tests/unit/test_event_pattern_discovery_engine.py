"""Tests for EventPatternDiscoveryEngine."""

from __future__ import annotations

from shieldops.observability.event_pattern_discovery_engine import (
    EventCategory,
    EventPatternDiscoveryEngine,
    PatternConfidence,
    PatternFrequency,
)


def _engine(**kw) -> EventPatternDiscoveryEngine:
    return EventPatternDiscoveryEngine(**kw)


class TestEnums:
    def test_pattern_frequency(self):
        assert PatternFrequency.DAILY == "daily"

    def test_pattern_confidence(self):
        assert PatternConfidence.CONFIRMED == "confirmed"

    def test_event_category(self):
        assert EventCategory.DEPLOYMENT == "deployment"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            pattern_id="p-1",
            event_sequence="deploy->alert",
        )
        assert rec.pattern_id == "p-1"
        assert rec.event_sequence == "deploy->alert"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                pattern_id=f"p-{i}",
                event_sequence="seq",
            )
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(
            pattern_id="p-1",
            event_sequence="deploy->alert",
        )
        result = eng.process("p-1")
        assert isinstance(result, dict)
        assert result["pattern_id"] == "p-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestDiscoverSequences:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            pattern_id="p-1",
            event_sequence="deploy->alert",
            occurrence_count=5,
        )
        result = eng.discover_sequences()
        assert isinstance(result, list)


class TestComputePatternFrequency:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            pattern_id="p-1",
            event_sequence="deploy->alert",
        )
        result = eng.compute_pattern_frequency("p-1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(
            pattern_id="p-1",
            event_sequence="seq",
        )
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            pattern_id="p-1",
            event_sequence="seq",
        )
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(
            pattern_id="p-1",
            event_sequence="seq",
        )
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0

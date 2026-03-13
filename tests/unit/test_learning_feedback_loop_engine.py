"""Tests for LearningFeedbackLoopEngine."""

from __future__ import annotations

from shieldops.knowledge.learning_feedback_loop_engine import (
    AdaptationSpeed,
    FeedbackSignal,
    LearningFeedbackLoopEngine,
    LoopStage,
)


def _engine(**kw) -> LearningFeedbackLoopEngine:
    return LearningFeedbackLoopEngine(**kw)


class TestEnums:
    def test_feedback_signal_values(self):
        assert isinstance(FeedbackSignal.POSITIVE, str)
        assert isinstance(FeedbackSignal.NEGATIVE, str)
        assert isinstance(FeedbackSignal.NEUTRAL, str)
        assert isinstance(FeedbackSignal.AMBIGUOUS, str)

    def test_loop_stage_values(self):
        assert isinstance(LoopStage.OBSERVE, str)
        assert isinstance(LoopStage.ORIENT, str)
        assert isinstance(LoopStage.DECIDE, str)
        assert isinstance(LoopStage.ACT, str)

    def test_adaptation_speed_values(self):
        assert isinstance(AdaptationSpeed.IMMEDIATE, str)
        assert isinstance(AdaptationSpeed.GRADUAL, str)
        assert isinstance(AdaptationSpeed.DELAYED, str)
        assert isinstance(AdaptationSpeed.NONE, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            agent_id="a1",
            signal=FeedbackSignal.POSITIVE,
            signal_strength=0.9,
        )
        assert r.agent_id == "a1"
        assert r.signal_strength == 0.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(agent_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(agent_id="a1")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        assert "total_records" in eng.get_stats()

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        eng.add_record(agent_id="a2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestProcessFeedbackSignal:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            signal=FeedbackSignal.POSITIVE,
            signal_strength=0.9,
        )
        result = eng.process_feedback_signal("a1")
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.process_feedback_signal("a1") == []


class TestComputeAdaptationRate:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            speed=AdaptationSpeed.IMMEDIATE,
        )
        eng.add_record(
            agent_id="a1",
            speed=AdaptationSpeed.GRADUAL,
        )
        result = eng.compute_adaptation_rate("a1")
        assert result["adaptation_rate"] == 0.5

    def test_empty(self):
        eng = _engine()
        result = eng.compute_adaptation_rate("a1")
        assert result["status"] == "no_data"


class TestDetectFeedbackStaleness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            speed=AdaptationSpeed.NONE,
        )
        result = eng.detect_feedback_staleness("a1")
        assert result["staleness_rate"] == 1.0

    def test_empty(self):
        eng = _engine()
        result = eng.detect_feedback_staleness("a1")
        assert result["status"] == "no_data"

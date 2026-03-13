"""Tests for EventReplayIntelligence."""

from __future__ import annotations

from shieldops.operations.event_replay_intelligence import (
    EventReplayIntelligence,
    IdempotencyStatus,
    ReplayScope,
    SafetyLevel,
)


def _engine(**kw) -> EventReplayIntelligence:
    return EventReplayIntelligence(**kw)


class TestEnums:
    def test_replay_scope_values(self):
        for v in ReplayScope:
            assert isinstance(v.value, str)

    def test_safety_level_values(self):
        for v in SafetyLevel:
            assert isinstance(v.value, str)

    def test_idempotency_status_values(self):
        for v in IdempotencyStatus:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(replay_id="r1")
        assert r.replay_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(replay_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().record_item()
        assert r.replay_scope == ReplayScope.PARTIAL


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(replay_id="r1", impact_score=50.0)
        a = eng.process(r.id)
        assert hasattr(a, "replay_id")
        assert a.replay_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(replay_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_risky_replays(self):
        eng = _engine()
        eng.record_item(
            replay_id="r1",
            safety_level=SafetyLevel.RISKY,
        )
        rpt = eng.generate_report()
        assert len(rpt.risky_replays) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(replay_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(replay_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeReplayImpactEstimate:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            replay_id="r1",
            impact_score=75.0,
            target_service="svc1",
        )
        result = eng.compute_replay_impact_estimate()
        assert len(result) == 1
        assert result[0]["total_impact"] == 75.0

    def test_empty(self):
        r = _engine().compute_replay_impact_estimate()
        assert r == []


class TestDetectIdempotencyViolations:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            replay_id="r1",
            idempotency_status=(IdempotencyStatus.VIOLATED),
        )
        result = eng.detect_idempotency_violations()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().detect_idempotency_violations()
        assert r == []


class TestRankReplayCandidatesBySafety:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            replay_id="r1",
            safety_level=SafetyLevel.SAFE,
        )
        eng.record_item(
            replay_id="r2",
            safety_level=SafetyLevel.BLOCKED,
        )
        result = eng.rank_replay_candidates_by_safety()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_replay_candidates_by_safety()
        assert r == []

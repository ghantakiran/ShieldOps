"""Tests for RiskScoreDecayRefreshEngine."""

from __future__ import annotations

from shieldops.security.risk_score_decay_refresh_engine import (
    DecayModel,
    RefreshTrigger,
    RiskScoreDecayAnalysis,
    RiskScoreDecayRecord,
    RiskScoreDecayRefreshEngine,
    RiskScoreDecayReport,
    ScoreStatus,
)


def _engine(**kw) -> RiskScoreDecayRefreshEngine:
    return RiskScoreDecayRefreshEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        entity_id="ent-001",
        decay_model=DecayModel.EXPONENTIAL,
        refresh_trigger=RefreshTrigger.TIME_BASED,
        score_status=ScoreStatus.STALE,
        original_score=0.9,
        current_score=0.6,
        decay_rate=0.05,
        age_hours=12.0,
    )
    assert isinstance(r, RiskScoreDecayRecord)
    assert r.entity_id == "ent-001"
    assert r.age_hours == 12.0
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(entity_id=f"e-{i}")
    assert len(eng._records) == 3


def test_process_found_exponential():
    eng = _engine()
    r = eng.add_record(
        entity_id="e-1",
        decay_model=DecayModel.EXPONENTIAL,
        score_status=ScoreStatus.STALE,
        original_score=1.0,
        current_score=0.6,
        decay_rate=0.1,
        age_hours=5.0,
    )
    result = eng.process(r.id)
    assert isinstance(result, RiskScoreDecayAnalysis)
    assert result.entity_id == "e-1"
    assert result.decayed_score >= 0
    assert result.needs_refresh is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("unknown")
    assert result == {"status": "not_found", "key": "unknown"}


def test_generate_report():
    eng = _engine()
    eng.add_record(entity_id="e1", score_status=ScoreStatus.STALE, current_score=0.5)
    eng.add_record(entity_id="e2", score_status=ScoreStatus.EXPIRED, current_score=0.2)
    eng.add_record(entity_id="e3", score_status=ScoreStatus.CURRENT, current_score=0.8)
    report = eng.generate_report()
    assert isinstance(report, RiskScoreDecayReport)
    assert report.total_records == 3
    assert report.avg_current_score > 0
    assert len(report.stale_entities) >= 2
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(score_status=ScoreStatus.CURRENT)
    eng.add_record(score_status=ScoreStatus.STALE)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "score_status_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(entity_id="e1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_evaluate_score_freshness():
    eng = _engine()
    eng.add_record(
        entity_id="e1",
        score_status=ScoreStatus.STALE,
        original_score=1.0,
        current_score=0.4,
        age_hours=24.0,
    )
    eng.add_record(
        entity_id="e1",
        score_status=ScoreStatus.CURRENT,
        original_score=0.9,
        current_score=0.85,
        age_hours=2.0,
    )
    eng.add_record(
        entity_id="e2",
        score_status=ScoreStatus.CURRENT,
        original_score=0.7,
        current_score=0.68,
        age_hours=1.0,
    )
    results = eng.evaluate_score_freshness()
    assert isinstance(results, list)
    assert len(results) == 2
    assert "staleness_ratio" in results[0]
    assert "avg_age_hours" in results[0]
    assert results[0]["staleness_ratio"] >= results[-1]["staleness_ratio"]


def test_detect_stale_risk_scores():
    eng = _engine()
    eng.add_record(entity_id="e1", score_status=ScoreStatus.STALE, age_hours=48.0)
    eng.add_record(entity_id="e2", score_status=ScoreStatus.CURRENT, age_hours=1.0)
    eng.add_record(entity_id="e3", score_status=ScoreStatus.EXPIRED, age_hours=168.0)
    results = eng.detect_stale_risk_scores()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["score_status"] in ("stale", "expired") for r in results)
    assert results[0]["age_hours"] >= results[-1]["age_hours"]


def test_optimize_refresh_schedules():
    eng = _engine()
    eng.add_record(
        entity_id="fast",
        decay_rate=0.2,
        original_score=0.9,
        refresh_trigger=RefreshTrigger.TIME_BASED,
    )
    eng.add_record(
        entity_id="slow",
        decay_rate=0.001,
        original_score=0.5,
        refresh_trigger=RefreshTrigger.MANUAL,
    )
    results = eng.optimize_refresh_schedules()
    assert isinstance(results, list)
    assert len(results) == 2
    # Faster decay -> shorter interval (sorted ascending)
    fast_entry = next(r for r in results if r["entity_id"] == "fast")
    slow_entry = next(r for r in results if r["entity_id"] == "slow")
    fast_interval = fast_entry["recommended_refresh_interval_h"]
    slow_interval = slow_entry["recommended_refresh_interval_h"]
    assert fast_interval <= slow_interval
    assert "avg_decay_rate" in results[0]

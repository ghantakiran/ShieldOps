"""Tests for LateralMovementRiskScorerEngine."""

from __future__ import annotations

from shieldops.security.lateral_movement_risk_scorer_engine import (
    DetectionMethod,
    LateralMovementAnalysis,
    LateralMovementRecord,
    LateralMovementReport,
    LateralMovementRiskScorerEngine,
    MovementPattern,
    RiskLevel,
)


def _engine(**kw) -> LateralMovementRiskScorerEngine:
    return LateralMovementRiskScorerEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        source_host="host-a",
        target_host="host-b",
        movement_pattern=MovementPattern.PASS_THE_HASH,
        detection_method=DetectionMethod.GRAPH_ANALYSIS,
        risk_level=RiskLevel.HIGH,
        risk_score=0.85,
        hop_count=3,
    )
    assert isinstance(r, LateralMovementRecord)
    assert r.source_host == "host-a"
    assert r.hop_count == 3
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(source_host=f"h-{i}", target_host="x")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        source_host="src",
        target_host="tgt",
        risk_level=RiskLevel.CRITICAL,
        risk_score=0.9,
        hop_count=4,
    )
    result = eng.process(r.id)
    assert isinstance(result, LateralMovementAnalysis)
    assert result.source_host == "src"
    assert result.composite_risk > 0
    assert result.chain_detected is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("missing")
    assert result == {"status": "not_found", "key": "missing"}


def test_generate_report():
    eng = _engine()
    eng.add_record(source_host="a", target_host="b", risk_level=RiskLevel.CRITICAL, risk_score=0.9)
    eng.add_record(source_host="c", target_host="d", risk_level=RiskLevel.MEDIUM, risk_score=0.5)
    eng.add_record(source_host="e", target_host="f", risk_level=RiskLevel.LOW, risk_score=0.2)
    report = eng.generate_report()
    assert isinstance(report, LateralMovementReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(risk_level=RiskLevel.HIGH)
    eng.add_record(risk_level=RiskLevel.LOW)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "risk_level_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(source_host="h1", target_host="h2")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_score_lateral_movement_risk():
    eng = _engine()
    eng.add_record(
        source_host="s1", target_host="t1", risk_level=RiskLevel.CRITICAL, risk_score=0.9
    )
    eng.add_record(source_host="s1", target_host="t2", risk_level=RiskLevel.HIGH, risk_score=0.7)
    eng.add_record(source_host="s2", target_host="t3", risk_level=RiskLevel.LOW, risk_score=0.2)
    results = eng.score_lateral_movement_risk()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["source_host"] == "s1"
    assert results[0]["total_risk_score"] > results[1]["total_risk_score"]
    assert "unique_targets" in results[0]


def test_detect_movement_chains():
    eng = _engine()
    eng.add_record(source_host="a", target_host="b", hop_count=5, risk_score=0.8)
    eng.add_record(source_host="c", target_host="d", hop_count=1, risk_score=0.6)
    eng.add_record(source_host="e", target_host="f", hop_count=3, risk_score=0.7)
    results = eng.detect_movement_chains()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["hop_count"] > 2 for r in results)
    assert results[0]["hop_count"] >= results[-1]["hop_count"]


def test_rank_paths_by_risk():
    eng = _engine()
    eng.add_record(source_host="a", target_host="b", risk_level=RiskLevel.CRITICAL, risk_score=0.9)
    eng.add_record(source_host="c", target_host="d", risk_level=RiskLevel.LOW, risk_score=0.2)
    eng.add_record(source_host="e", target_host="f", risk_level=RiskLevel.HIGH, risk_score=0.7)
    results = eng.rank_paths_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["composite_risk"] >= results[1]["composite_risk"]

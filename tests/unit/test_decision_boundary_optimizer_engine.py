"""Tests for DecisionBoundaryOptimizerEngine."""

from __future__ import annotations

from shieldops.analytics.decision_boundary_optimizer_engine import (
    BoundaryQuality,
    BoundaryType,
    DecisionBoundaryOptimizerEngine,
)


def _engine(**kw) -> DecisionBoundaryOptimizerEngine:
    return DecisionBoundaryOptimizerEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", accuracy_score=0.88)
    assert r.agent_id == "a1"
    assert r.accuracy_score == 0.88


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        agent_id="a1",
        boundary_type=BoundaryType.NONLINEAR,
        accuracy_score=0.9,
        false_positive_rate=0.05,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.boundary_score >= 0


def test_process_not_found():
    result = _engine().process("missing-id")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        boundary_type=BoundaryType.LINEAR,
        boundary_quality=BoundaryQuality.NOISY,
        accuracy_score=0.6,
    )
    eng.add_record(
        agent_id="a2",
        boundary_type=BoundaryType.ENSEMBLE,
        boundary_quality=BoundaryQuality.OPTIMAL,
        accuracy_score=0.95,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "noisy" in rpt.by_boundary_quality
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", boundary_type=BoundaryType.ADAPTIVE)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "adaptive" in stats["boundary_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_boundary_quality():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        accuracy_score=0.9,
        false_positive_rate=0.02,
        false_negative_rate=0.03,
        boundary_quality=BoundaryQuality.SHARP,
    )
    eng.add_record(
        agent_id="a2",
        accuracy_score=0.6,
        false_positive_rate=0.2,
        false_negative_rate=0.25,
        boundary_quality=BoundaryQuality.FUZZY,
    )
    result = eng.evaluate_boundary_quality()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "avg_accuracy" in result[0]
    assert "f1_approx" in result[0]
    assert result[0]["avg_accuracy"] >= result[1]["avg_accuracy"]


def test_detect_boundary_drift():
    eng = _engine()
    eng.add_record(agent_id="a1", accuracy_score=0.9, false_positive_rate=0.05)
    eng.add_record(agent_id="a1", accuracy_score=0.6, false_positive_rate=0.3)
    eng.add_record(agent_id="a2", accuracy_score=0.85, false_positive_rate=0.05)
    eng.add_record(agent_id="a2", accuracy_score=0.86, false_positive_rate=0.05)
    result = eng.detect_boundary_drift()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "is_drifting" in result[0]
    assert "drift_severity" in result[0]


def test_optimize_decision_thresholds():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        boundary_type=BoundaryType.LINEAR,
        accuracy_score=0.8,
        false_positive_rate=0.3,
        false_negative_rate=0.05,
    )
    eng.add_record(
        agent_id="a2",
        boundary_type=BoundaryType.NONLINEAR,
        accuracy_score=0.9,
        false_positive_rate=0.05,
        false_negative_rate=0.04,
    )
    result = eng.optimize_decision_thresholds()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "recommended_threshold" in result[0]
    assert "rationale" in result[0]
    assert 0.0 <= result[0]["recommended_threshold"] <= 1.0

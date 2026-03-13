"""Tests for InvestigationTrajectoryScorerEngine."""

from __future__ import annotations

from shieldops.observability.investigation_trajectory_scorer_engine import (
    DeviationType,
    InvestigationTrajectoryScorerAnalysis,
    InvestigationTrajectoryScorerEngine,
    InvestigationTrajectoryScorerRecord,
    InvestigationTrajectoryScorerReport,
    ScoringDimension,
    TrajectoryQuality,
)


def test_add_record() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    rec = engine.add_record(
        investigation_id="inv-001",
        trajectory_quality=TrajectoryQuality.OPTIMAL,
        scoring_dimension=ScoringDimension.EFFICIENCY,
        deviation_type=DeviationType.UNNECESSARY_DETOUR,
        dimension_score=0.95,
        steps_taken=5,
        optimal_steps=5,
    )
    assert isinstance(rec, InvestigationTrajectoryScorerRecord)
    assert rec.investigation_id == "inv-001"
    assert rec.dimension_score == 0.95


def test_process() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    rec = engine.add_record(
        investigation_id="inv-002",
        trajectory_quality=TrajectoryQuality.WASTEFUL,
        scoring_dimension=ScoringDimension.COMPLETENESS,
        dimension_score=0.3,
        steps_taken=20,
        optimal_steps=5,
    )
    result = engine.process(rec.id)
    assert isinstance(result, InvestigationTrajectoryScorerAnalysis)
    assert result.investigation_id == "inv-002"
    assert result.overall_score < 0.3
    assert result.efficiency_ratio < 1.0


def test_process_not_found() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    for inv_id, tq, sd, dt, score in [
        (
            "i1",
            TrajectoryQuality.OPTIMAL,
            ScoringDimension.EFFICIENCY,
            DeviationType.UNNECESSARY_DETOUR,
            0.95,
        ),
        (
            "i2",
            TrajectoryQuality.GOOD,
            ScoringDimension.COMPLETENESS,
            DeviationType.MISSED_SHORTCUT,
            0.7,
        ),
        (
            "i3",
            TrajectoryQuality.SUBOPTIMAL,
            ScoringDimension.ACCURACY,
            DeviationType.WRONG_BRANCH,
            0.45,
        ),
        (
            "i4",
            TrajectoryQuality.WASTEFUL,
            ScoringDimension.TIMELINESS,
            DeviationType.PREMATURE_CONCLUSION,
            0.2,
        ),
    ]:
        engine.add_record(
            investigation_id=inv_id,
            trajectory_quality=tq,
            scoring_dimension=sd,
            deviation_type=dt,
            dimension_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, InvestigationTrajectoryScorerReport)
    assert report.total_records == 4
    assert "optimal" in report.by_trajectory_quality


def test_get_stats() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    engine.add_record(trajectory_quality=TrajectoryQuality.OPTIMAL, dimension_score=0.9)
    engine.add_record(trajectory_quality=TrajectoryQuality.WASTEFUL, dimension_score=0.2)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "trajectory_quality_distribution" in stats


def test_clear_data() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    engine.add_record(investigation_id="inv-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_score_investigation_trajectory() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    engine.add_record(
        investigation_id="inv-A", trajectory_quality=TrajectoryQuality.OPTIMAL, dimension_score=1.0
    )
    engine.add_record(
        investigation_id="inv-A", trajectory_quality=TrajectoryQuality.OPTIMAL, dimension_score=0.9
    )
    engine.add_record(
        investigation_id="inv-B", trajectory_quality=TrajectoryQuality.WASTEFUL, dimension_score=0.5
    )
    results = engine.score_investigation_trajectory()
    assert isinstance(results, list)
    assert results[0]["investigation_id"] == "inv-A"
    assert results[0]["avg_trajectory_score"] >= results[-1]["avg_trajectory_score"]


def test_identify_trajectory_inefficiencies() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    engine.add_record(
        investigation_id="inefficient-1",
        trajectory_quality=TrajectoryQuality.WASTEFUL,
        deviation_type=DeviationType.WRONG_BRANCH,
        steps_taken=20,
        optimal_steps=5,
    )
    engine.add_record(
        investigation_id="efficient-1",
        trajectory_quality=TrajectoryQuality.OPTIMAL,
        steps_taken=5,
        optimal_steps=5,
    )
    results = engine.identify_trajectory_inefficiencies()
    assert isinstance(results, list)
    assert any(r["investigation_id"] == "inefficient-1" for r in results)
    assert all(r["trajectory_quality"] in ("wasteful", "suboptimal") for r in results)


def test_compare_trajectories() -> None:
    engine = InvestigationTrajectoryScorerEngine()
    engine.add_record(investigation_id="inv-X", dimension_score=0.9, steps_taken=5)
    engine.add_record(investigation_id="inv-Y", dimension_score=0.4, steps_taken=15)
    results = engine.compare_trajectories()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["avg_score"] >= results[-1]["avg_score"]

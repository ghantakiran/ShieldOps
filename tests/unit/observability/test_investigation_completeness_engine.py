"""Tests for InvestigationCompletenessEngine."""

from __future__ import annotations

from shieldops.observability.investigation_completeness_engine import (
    CompletenessLevel,
    GapType,
    InvestigationCompletenessAnalysis,
    InvestigationCompletenessEngine,
    InvestigationCompletenessRecord,
    InvestigationCompletenessReport,
    VerificationStatus,
)


def test_add_record() -> None:
    engine = InvestigationCompletenessEngine()
    rec = engine.add_record(
        investigation_id="inv-001",
        completeness_level=CompletenessLevel.THOROUGH,
        gap_type=GapType.MISSING_DATA,
        verification_status=VerificationStatus.VERIFIED,
        completeness_score=0.95,
        open_gap_count=0,
        hypothesis_count=5,
    )
    assert isinstance(rec, InvestigationCompletenessRecord)
    assert rec.investigation_id == "inv-001"
    assert rec.open_gap_count == 0


def test_process_complete() -> None:
    engine = InvestigationCompletenessEngine()
    rec = engine.add_record(
        investigation_id="inv-002",
        completeness_level=CompletenessLevel.THOROUGH,
        completeness_score=0.95,
        open_gap_count=0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, InvestigationCompletenessAnalysis)
    assert result.investigation_id == "inv-002"
    assert result.is_complete is True


def test_process_incomplete() -> None:
    engine = InvestigationCompletenessEngine()
    rec = engine.add_record(
        investigation_id="inv-003",
        completeness_level=CompletenessLevel.SUPERFICIAL,
        completeness_score=0.2,
        open_gap_count=5,
    )
    result = engine.process(rec.id)
    assert isinstance(result, InvestigationCompletenessAnalysis)
    assert result.is_complete is False


def test_process_not_found() -> None:
    engine = InvestigationCompletenessEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = InvestigationCompletenessEngine()
    for inv_id, cl, gt, vs, score, gaps in [
        (
            "i1",
            CompletenessLevel.THOROUGH,
            GapType.MISSING_DATA,
            VerificationStatus.VERIFIED,
            0.95,
            0,
        ),
        (
            "i2",
            CompletenessLevel.ADEQUATE,
            GapType.UNEXPLORED_HYPOTHESIS,
            VerificationStatus.PARTIALLY_VERIFIED,
            0.7,
            1,
        ),
        (
            "i3",
            CompletenessLevel.INCOMPLETE,
            GapType.UNVERIFIED_ASSUMPTION,
            VerificationStatus.UNVERIFIED,
            0.4,
            3,
        ),
        (
            "i4",
            CompletenessLevel.SUPERFICIAL,
            GapType.UNTESTED_ALTERNATIVE,
            VerificationStatus.CONTRADICTED,
            0.1,
            7,
        ),
    ]:
        engine.add_record(
            investigation_id=inv_id,
            completeness_level=cl,
            gap_type=gt,
            verification_status=vs,
            completeness_score=score,
            open_gap_count=gaps,
        )
    report = engine.generate_report()
    assert isinstance(report, InvestigationCompletenessReport)
    assert report.total_records == 4
    assert "thorough" in report.by_completeness_level
    assert len(report.incomplete_investigations) >= 1


def test_get_stats() -> None:
    engine = InvestigationCompletenessEngine()
    engine.add_record(completeness_level=CompletenessLevel.THOROUGH, completeness_score=0.9)
    engine.add_record(completeness_level=CompletenessLevel.SUPERFICIAL, completeness_score=0.1)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "completeness_level_distribution" in stats


def test_clear_data() -> None:
    engine = InvestigationCompletenessEngine()
    engine.add_record(investigation_id="inv-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_assess_investigation_completeness() -> None:
    engine = InvestigationCompletenessEngine()
    engine.add_record(
        investigation_id="inv-A",
        completeness_level=CompletenessLevel.THOROUGH,
        completeness_score=0.95,
        open_gap_count=0,
    )
    engine.add_record(
        investigation_id="inv-A",
        completeness_level=CompletenessLevel.ADEQUATE,
        completeness_score=0.75,
        open_gap_count=1,
    )
    engine.add_record(
        investigation_id="inv-B",
        completeness_level=CompletenessLevel.SUPERFICIAL,
        completeness_score=0.2,
        open_gap_count=5,
    )
    results = engine.assess_investigation_completeness()
    assert isinstance(results, list)
    assert results[0]["investigation_id"] == "inv-A"
    assert results[0]["avg_completeness_score"] >= results[-1]["avg_completeness_score"]


def test_enumerate_open_gaps() -> None:
    engine = InvestigationCompletenessEngine()
    engine.add_record(gap_type=GapType.MISSING_DATA, open_gap_count=3)
    engine.add_record(gap_type=GapType.MISSING_DATA, open_gap_count=2)
    engine.add_record(gap_type=GapType.UNEXPLORED_HYPOTHESIS, open_gap_count=1)
    results = engine.enumerate_open_gaps()
    assert isinstance(results, list)
    missing_data = next(r for r in results if r["gap_type"] == "missing_data")
    assert missing_data["total_open_gaps"] == 5
    assert results[0]["total_open_gaps"] >= results[-1]["total_open_gaps"]


def test_recommend_completion_actions() -> None:
    engine = InvestigationCompletenessEngine()
    engine.add_record(
        investigation_id="inv-X",
        gap_type=GapType.MISSING_DATA,
        completeness_score=0.4,
        open_gap_count=2,
    )
    engine.add_record(
        investigation_id="inv-Y",
        gap_type=GapType.UNEXPLORED_HYPOTHESIS,
        completeness_score=0.9,
        open_gap_count=0,
    )
    results = engine.recommend_completion_actions()
    assert isinstance(results, list)
    inv_x = next(r for r in results if r["investigation_id"] == "inv-X")
    assert len(inv_x["recommended_actions"]) >= 1
    assert "open_gap_types" in inv_x

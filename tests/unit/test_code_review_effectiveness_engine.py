"""Tests for CodeReviewEffectivenessEngine."""

from __future__ import annotations

from shieldops.analytics.code_review_effectiveness_engine import (
    BottleneckType,
    CodeReviewEffectivenessEngine,
    ReviewDepth,
    ReviewOutcome,
)


def _engine(**kw) -> CodeReviewEffectivenessEngine:
    return CodeReviewEffectivenessEngine(**kw)


class TestEnums:
    def test_review_outcome_values(self):
        for v in ReviewOutcome:
            assert isinstance(v.value, str)

    def test_review_depth_values(self):
        for v in ReviewDepth:
            assert isinstance(v.value, str)

    def test_bottleneck_type_values(self):
        for v in BottleneckType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(review_id="r1")
        assert r.review_id == "r1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            review_id="r1",
            reviewer_id="rev1",
            quality_score=90.0,
            comments_count=5,
        )
        assert r.quality_score == 90.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(review_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            review_id="r1",
            reviewer_id="rev1",
            quality_score=85.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "reviewer_id")
        assert a.reviewer_id == "rev1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(review_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(review_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(review_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeReviewQualityScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            reviewer_id="rev1",
            quality_score=90.0,
            comments_count=10,
        )
        result = eng.compute_review_quality_score()
        assert len(result) == 1
        assert result[0]["quality_score"] == 90.0

    def test_empty(self):
        r = _engine().compute_review_quality_score()
        assert r == []


class TestDetectReviewBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            review_id="r1",
            bottleneck=BottleneckType.QUEUE_TIME,
            review_time_hours=8.0,
        )
        result = eng.detect_review_bottlenecks()
        assert len(result) == 1
        assert result[0]["total_hours"] == 8.0

    def test_empty(self):
        r = _engine().detect_review_bottlenecks()
        assert r == []


class TestRankReviewersByEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            reviewer_id="rev1",
            quality_score=90.0,
        )
        eng.add_record(
            reviewer_id="rev2",
            quality_score=70.0,
        )
        result = eng.rank_reviewers_by_effectiveness()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_reviewers_by_effectiveness()
        assert r == []

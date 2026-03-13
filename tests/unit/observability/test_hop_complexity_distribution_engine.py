"""Tests for HopComplexityDistributionEngine."""

from __future__ import annotations

from shieldops.observability.hop_complexity_distribution_engine import (
    AnalysisPeriod,
    ComplexityBucket,
    DistributionTrend,
    HopComplexityDistributionAnalysis,
    HopComplexityDistributionEngine,
    HopComplexityDistributionRecord,
    HopComplexityDistributionReport,
)


def test_add_record() -> None:
    engine = HopComplexityDistributionEngine()
    rec = engine.add_record(
        investigation_id="inv-001",
        complexity_bucket=ComplexityBucket.TWO_HOP,
        distribution_trend=DistributionTrend.STABLE,
        analysis_period=AnalysisPeriod.DAILY,
        hop_count=2,
        period_label="2026-03-13",
    )
    assert isinstance(rec, HopComplexityDistributionRecord)
    assert rec.investigation_id == "inv-001"
    assert rec.hop_count == 2


def test_process() -> None:
    engine = HopComplexityDistributionEngine()
    rec = engine.add_record(
        investigation_id="inv-002",
        complexity_bucket=ComplexityBucket.FOUR_PLUS_HOP,
        distribution_trend=DistributionTrend.SHIFTING_COMPLEX,
        analysis_period=AnalysisPeriod.WEEKLY,
        hop_count=5,
    )
    result = engine.process(rec.id)
    assert isinstance(result, HopComplexityDistributionAnalysis)
    assert result.investigation_id == "inv-002"
    assert result.shift_detected is True


def test_process_stable() -> None:
    engine = HopComplexityDistributionEngine()
    rec = engine.add_record(
        investigation_id="inv-003",
        complexity_bucket=ComplexityBucket.ONE_HOP,
        distribution_trend=DistributionTrend.STABLE,
        hop_count=1,
    )
    result = engine.process(rec.id)
    assert isinstance(result, HopComplexityDistributionAnalysis)
    assert result.shift_detected is False


def test_process_not_found() -> None:
    engine = HopComplexityDistributionEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = HopComplexityDistributionEngine()
    for inv_id, cb, dt, ap, hops in [
        ("i1", ComplexityBucket.ONE_HOP, DistributionTrend.STABLE, AnalysisPeriod.HOURLY, 1),
        (
            "i2",
            ComplexityBucket.TWO_HOP,
            DistributionTrend.SHIFTING_SIMPLE,
            AnalysisPeriod.DAILY,
            2,
        ),
        (
            "i3",
            ComplexityBucket.THREE_HOP,
            DistributionTrend.SHIFTING_COMPLEX,
            AnalysisPeriod.WEEKLY,
            3,
        ),
        (
            "i4",
            ComplexityBucket.FOUR_PLUS_HOP,
            DistributionTrend.BIMODAL,
            AnalysisPeriod.MONTHLY,
            5,
        ),
    ]:
        engine.add_record(
            investigation_id=inv_id,
            complexity_bucket=cb,
            distribution_trend=dt,
            analysis_period=ap,
            hop_count=hops,
        )
    report = engine.generate_report()
    assert isinstance(report, HopComplexityDistributionReport)
    assert report.total_records == 4
    assert "one_hop" in report.by_complexity_bucket
    assert "one_hop" in report.optimal_ratio_delta


def test_get_stats() -> None:
    engine = HopComplexityDistributionEngine()
    engine.add_record(complexity_bucket=ComplexityBucket.ONE_HOP, hop_count=1)
    engine.add_record(complexity_bucket=ComplexityBucket.THREE_HOP, hop_count=3)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "complexity_bucket_distribution" in stats


def test_clear_data() -> None:
    engine = HopComplexityDistributionEngine()
    engine.add_record(investigation_id="inv-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_compute_hop_distribution() -> None:
    engine = HopComplexityDistributionEngine()
    engine.add_record(
        complexity_bucket=ComplexityBucket.ONE_HOP,
        hop_count=1,
        period_label="day-1",
    )
    engine.add_record(
        complexity_bucket=ComplexityBucket.TWO_HOP,
        hop_count=2,
        period_label="day-1",
    )
    engine.add_record(
        complexity_bucket=ComplexityBucket.ONE_HOP,
        hop_count=1,
        period_label="day-2",
    )
    results = engine.compute_hop_distribution()
    assert isinstance(results, list)
    day1 = next(r for r in results if r["period_label"] == "day-1")
    assert day1["total"] == 2
    assert "bucket_ratios" in day1


def test_detect_distribution_shift() -> None:
    engine = HopComplexityDistributionEngine()
    engine.add_record(
        distribution_trend=DistributionTrend.SHIFTING_COMPLEX,
        complexity_bucket=ComplexityBucket.FOUR_PLUS_HOP,
        period_label="week-1",
        hop_count=5,
    )
    engine.add_record(
        distribution_trend=DistributionTrend.STABLE,
        complexity_bucket=ComplexityBucket.ONE_HOP,
        period_label="week-2",
        hop_count=1,
    )
    engine.add_record(
        distribution_trend=DistributionTrend.BIMODAL,
        complexity_bucket=ComplexityBucket.THREE_HOP,
        period_label="week-3",
        hop_count=3,
    )
    results = engine.detect_distribution_shift()
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r["distribution_trend"] in ("shifting_complex", "bimodal") for r in results)


def test_compare_to_optimal_ratio() -> None:
    engine = HopComplexityDistributionEngine()
    # Add 4 one-hop, 3 two-hop, 2 three-hop, 1 four-plus — matching 4:3:2:1
    for _ in range(4):
        engine.add_record(complexity_bucket=ComplexityBucket.ONE_HOP)
    for _ in range(3):
        engine.add_record(complexity_bucket=ComplexityBucket.TWO_HOP)
    for _ in range(2):
        engine.add_record(complexity_bucket=ComplexityBucket.THREE_HOP)
    engine.add_record(complexity_bucket=ComplexityBucket.FOUR_PLUS_HOP)
    results = engine.compare_to_optimal_ratio()
    assert isinstance(results, list)
    assert len(results) == 4
    assert all("delta" in r for r in results)
    assert all("status" in r for r in results)
    # With 4:3:2:1, deltas should be near 0
    one_hop = next(r for r in results if r["complexity_bucket"] == "one_hop")
    assert abs(one_hop["delta"]) < 0.01

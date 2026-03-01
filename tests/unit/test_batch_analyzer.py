"""Tests for shieldops.changes.batch_analyzer — ChangeBatchAnalyzer."""

from __future__ import annotations

from shieldops.changes.batch_analyzer import (
    BatchConflict,
    BatchRecord,
    BatchRisk,
    BatchType,
    ChangeBatchAnalyzer,
    ChangeBatchReport,
    ConflictType,
)


def _engine(**kw) -> ChangeBatchAnalyzer:
    return ChangeBatchAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # BatchRisk (5)
    def test_risk_critical(self):
        assert BatchRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert BatchRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert BatchRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert BatchRisk.LOW == "low"

    def test_risk_safe(self):
        assert BatchRisk.SAFE == "safe"

    # BatchType (5)
    def test_type_sequential(self):
        assert BatchType.SEQUENTIAL == "sequential"

    def test_type_parallel(self):
        assert BatchType.PARALLEL == "parallel"

    def test_type_mixed(self):
        assert BatchType.MIXED == "mixed"

    def test_type_atomic(self):
        assert BatchType.ATOMIC == "atomic"

    def test_type_phased(self):
        assert BatchType.PHASED == "phased"

    # ConflictType (5)
    def test_conflict_resource(self):
        assert ConflictType.RESOURCE == "resource"

    def test_conflict_dependency(self):
        assert ConflictType.DEPENDENCY == "dependency"

    def test_conflict_timing(self):
        assert ConflictType.TIMING == "timing"

    def test_conflict_configuration(self):
        assert ConflictType.CONFIGURATION == "configuration"

    def test_conflict_schema(self):
        assert ConflictType.SCHEMA == "schema"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_batch_record_defaults(self):
        r = BatchRecord()
        assert r.id
        assert r.batch_name == ""
        assert r.batch_type == BatchType.SEQUENTIAL
        assert r.risk == BatchRisk.LOW
        assert r.change_count == 0
        assert r.risk_score == 0.0
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_batch_conflict_defaults(self):
        c = BatchConflict()
        assert c.id
        assert c.batch_id == ""
        assert c.conflict_type == ConflictType.RESOURCE
        assert c.severity == BatchRisk.LOW
        assert c.description == ""
        assert c.created_at > 0

    def test_report_defaults(self):
        r = ChangeBatchReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_conflicts == 0
        assert r.avg_risk_score == 0.0
        assert r.high_risk_batches == 0
        assert r.by_type == {}
        assert r.by_risk == {}
        assert r.risky_teams == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_batch
# -------------------------------------------------------------------


class TestRecordBatch:
    def test_basic(self):
        eng = _engine()
        r = eng.record_batch(
            "release-1.0",
            batch_type=BatchType.PHASED,
            risk=BatchRisk.HIGH,
            risk_score=80.0,
            team="platform",
        )
        assert r.batch_name == "release-1.0"
        assert r.batch_type == BatchType.PHASED
        assert r.risk == BatchRisk.HIGH
        assert r.risk_score == 80.0
        assert r.team == "platform"

    def test_change_count_stored(self):
        eng = _engine()
        r = eng.record_batch("batch-x", change_count=12)
        assert r.change_count == 12

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_batch(f"batch-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_batch
# -------------------------------------------------------------------


class TestGetBatch:
    def test_found(self):
        eng = _engine()
        r = eng.record_batch("batch-a")
        assert eng.get_batch(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_batch("nonexistent") is None


# -------------------------------------------------------------------
# list_batches
# -------------------------------------------------------------------


class TestListBatches:
    def test_list_all(self):
        eng = _engine()
        eng.record_batch("batch-a")
        eng.record_batch("batch-b")
        assert len(eng.list_batches()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_batch("batch-a", batch_type=BatchType.ATOMIC)
        eng.record_batch("batch-b", batch_type=BatchType.SEQUENTIAL)
        results = eng.list_batches(batch_type=BatchType.ATOMIC)
        assert len(results) == 1

    def test_filter_by_risk(self):
        eng = _engine()
        eng.record_batch("batch-a", risk=BatchRisk.CRITICAL)
        eng.record_batch("batch-b", risk=BatchRisk.LOW)
        results = eng.list_batches(risk=BatchRisk.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_batch("batch-a", team="infra")
        eng.record_batch("batch-b", team="frontend")
        results = eng.list_batches(team="infra")
        assert len(results) == 1


# -------------------------------------------------------------------
# add_conflict
# -------------------------------------------------------------------


class TestAddConflict:
    def test_basic(self):
        eng = _engine()
        c = eng.add_conflict(
            "batch-id-1",
            conflict_type=ConflictType.SCHEMA,
            severity=BatchRisk.HIGH,
            description="Schema conflict detected",
        )
        assert c.batch_id == "batch-id-1"
        assert c.conflict_type == ConflictType.SCHEMA
        assert c.severity == BatchRisk.HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_conflict(f"batch-{i}")
        assert len(eng._conflicts) == 2


# -------------------------------------------------------------------
# analyze_batch_risk
# -------------------------------------------------------------------


class TestAnalyzeBatchRisk:
    def test_groups_by_type(self):
        eng = _engine()
        eng.record_batch("b1", batch_type=BatchType.PARALLEL, risk_score=60.0)
        eng.record_batch("b2", batch_type=BatchType.PARALLEL, risk_score=80.0)
        eng.record_batch("b3", batch_type=BatchType.ATOMIC, risk_score=20.0)
        results = eng.analyze_batch_risk()
        types = {r["batch_type"] for r in results}
        assert "parallel" in types
        assert "atomic" in types

    def test_sorted_desc(self):
        eng = _engine()
        eng.record_batch("b1", batch_type=BatchType.PHASED, risk_score=90.0)
        eng.record_batch("b2", batch_type=BatchType.MIXED, risk_score=10.0)
        results = eng.analyze_batch_risk()
        assert results[0]["avg_risk_score"] >= results[-1]["avg_risk_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_batch_risk() == []


# -------------------------------------------------------------------
# identify_high_risk_batches
# -------------------------------------------------------------------


class TestIdentifyHighRiskBatches:
    def test_finds_above_threshold(self):
        eng = _engine(max_batch_risk_score=75.0)
        eng.record_batch("safe-batch", risk_score=50.0, team="ops")
        eng.record_batch("risky-batch", risk_score=90.0, team="ops")
        results = eng.identify_high_risk_batches()
        assert len(results) == 1
        assert results[0]["batch_name"] == "risky-batch"

    def test_empty_when_all_safe(self):
        eng = _engine(max_batch_risk_score=75.0)
        eng.record_batch("fine-batch", risk_score=30.0)
        assert eng.identify_high_risk_batches() == []

    def test_empty_no_records(self):
        eng = _engine()
        assert eng.identify_high_risk_batches() == []


# -------------------------------------------------------------------
# rank_by_risk_score
# -------------------------------------------------------------------


class TestRankByRiskScore:
    def test_groups_by_team(self):
        eng = _engine()
        eng.record_batch("b1", team="infra", risk_score=70.0)
        eng.record_batch("b2", team="frontend", risk_score=30.0)
        results = eng.rank_by_risk_score()
        assert results[0]["team"] == "infra"

    def test_averages_correctly(self):
        eng = _engine()
        eng.record_batch("b1", team="ops", risk_score=40.0)
        eng.record_batch("b2", team="ops", risk_score=60.0)
        results = eng.rank_by_risk_score()
        assert results[0]["avg_risk_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# -------------------------------------------------------------------
# detect_batch_trends
# -------------------------------------------------------------------


class TestDetectBatchTrends:
    def test_detects_worsening(self):
        eng = _engine()
        for _ in range(3):
            eng.record_batch("b", team="ops", risk_score=20.0)
        for _ in range(3):
            eng.record_batch("b", team="ops", risk_score=90.0)
        results = eng.detect_batch_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "worsening"

    def test_no_trend_below_delta(self):
        eng = _engine()
        for _ in range(4):
            eng.record_batch("b", team="ops", risk_score=50.0)
        results = eng.detect_batch_trends()
        assert results == []

    def test_too_few_records(self):
        eng = _engine()
        eng.record_batch("b1", team="ops")
        assert eng.detect_batch_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_batch_risk_score=75.0)
        eng.record_batch("b1", risk=BatchRisk.CRITICAL, risk_score=90.0, team="infra")
        eng.record_batch("b2", risk=BatchRisk.LOW, risk_score=10.0, team="frontend")
        eng.add_conflict("batch-id-1", conflict_type=ConflictType.TIMING)
        report = eng.generate_report()
        assert isinstance(report, ChangeBatchReport)
        assert report.total_records == 2
        assert report.total_conflicts == 1
        assert report.high_risk_batches == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable" in report.recommendations[0]

    def test_risky_teams_populated(self):
        eng = _engine(max_batch_risk_score=50.0)
        eng.record_batch("b1", risk_score=80.0, team="sre")
        report = eng.generate_report()
        assert "sre" in report.risky_teams


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_batch("b1")
        eng.add_conflict("b1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._conflicts) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_batches"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["risk_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_batch("b1", risk=BatchRisk.HIGH, team="ops")
        eng.record_batch("b2", risk=BatchRisk.LOW, team="frontend")
        eng.add_conflict("b1")
        stats = eng.get_stats()
        assert stats["total_batches"] == 2
        assert stats["total_conflicts"] == 1
        assert stats["unique_teams"] == 2

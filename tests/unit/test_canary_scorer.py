"""Tests for shieldops.changes.canary_scorer — DeploymentCanaryScorer."""

from __future__ import annotations

from shieldops.changes.canary_scorer import (
    CanaryMetric,
    CanaryRecord,
    CanaryScorerReport,
    CanaryStage,
    CanaryVerdict,
    DeploymentCanaryScorer,
    MetricComparison,
)


def _engine(**kw) -> DeploymentCanaryScorer:
    return DeploymentCanaryScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CanaryMetric (5)
    def test_metric_error_rate(self):
        assert CanaryMetric.ERROR_RATE == "error_rate"

    def test_metric_latency(self):
        assert CanaryMetric.LATENCY == "latency"

    def test_metric_throughput(self):
        assert CanaryMetric.THROUGHPUT == "throughput"

    def test_metric_resource_usage(self):
        assert CanaryMetric.RESOURCE_USAGE == "resource_usage"

    def test_metric_custom(self):
        assert CanaryMetric.CUSTOM == "custom"

    # CanaryVerdict (5)
    def test_verdict_promote(self):
        assert CanaryVerdict.PROMOTE == "promote"

    def test_verdict_rollback(self):
        assert CanaryVerdict.ROLLBACK == "rollback"

    def test_verdict_extend(self):
        assert CanaryVerdict.EXTEND == "extend"

    def test_verdict_manual_review(self):
        assert CanaryVerdict.MANUAL_REVIEW == "manual_review"

    def test_verdict_inconclusive(self):
        assert CanaryVerdict.INCONCLUSIVE == "inconclusive"

    # CanaryStage (5)
    def test_stage_baseline(self):
        assert CanaryStage.BASELINE == "baseline"

    def test_stage_1pct(self):
        assert CanaryStage.CANARY_1PCT == "canary_1pct"

    def test_stage_5pct(self):
        assert CanaryStage.CANARY_5PCT == "canary_5pct"

    def test_stage_25pct(self):
        assert CanaryStage.CANARY_25PCT == "canary_25pct"

    def test_stage_full_rollout(self):
        assert CanaryStage.FULL_ROLLOUT == "full_rollout"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_canary_record_defaults(self):
        r = CanaryRecord()
        assert r.id
        assert r.deployment_id == ""
        assert r.service == ""
        assert r.stage == CanaryStage.BASELINE
        assert r.canary_score == 0.0
        assert r.verdict == CanaryVerdict.INCONCLUSIVE
        assert r.team == ""
        assert r.duration_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_metric_comparison_defaults(self):
        m = MetricComparison()
        assert m.id
        assert m.deployment_id == ""
        assert m.metric == CanaryMetric.ERROR_RATE
        assert m.baseline_value == 0.0
        assert m.canary_value == 0.0
        assert m.deviation_pct == 0.0
        assert m.created_at > 0

    def test_report_defaults(self):
        r = CanaryScorerReport()
        assert r.total_records == 0
        assert r.total_comparisons == 0
        assert r.avg_canary_score == 0.0
        assert r.by_verdict == {}
        assert r.by_stage == {}
        assert r.by_metric == {}
        assert r.failed_canaries == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_canary
# -------------------------------------------------------------------


class TestRecordCanary:
    def test_basic(self):
        eng = _engine()
        r = eng.record_canary(
            "dep-001",
            "svc-a",
            stage=CanaryStage.CANARY_5PCT,
            canary_score=92.0,
            verdict=CanaryVerdict.PROMOTE,
        )
        assert r.deployment_id == "dep-001"
        assert r.service == "svc-a"
        assert r.canary_score == 92.0
        assert r.verdict == CanaryVerdict.PROMOTE

    def test_with_team(self):
        eng = _engine()
        r = eng.record_canary("dep-002", "svc-b", team="platform")
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_canary(f"dep-{i}", f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_canary
# -------------------------------------------------------------------


class TestGetCanary:
    def test_found(self):
        eng = _engine()
        r = eng.record_canary("dep-001", "svc-a")
        assert eng.get_canary(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_canary("nonexistent") is None


# -------------------------------------------------------------------
# list_canaries
# -------------------------------------------------------------------


class TestListCanaries:
    def test_list_all(self):
        eng = _engine()
        eng.record_canary("dep-001", "svc-a")
        eng.record_canary("dep-002", "svc-b")
        assert len(eng.list_canaries()) == 2

    def test_filter_by_verdict(self):
        eng = _engine()
        eng.record_canary(
            "dep-001",
            "svc-a",
            verdict=CanaryVerdict.PROMOTE,
        )
        eng.record_canary(
            "dep-002",
            "svc-b",
            verdict=CanaryVerdict.ROLLBACK,
        )
        results = eng.list_canaries(verdict=CanaryVerdict.PROMOTE)
        assert len(results) == 1

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_canary(
            "dep-001",
            "svc-a",
            stage=CanaryStage.BASELINE,
        )
        eng.record_canary(
            "dep-002",
            "svc-b",
            stage=CanaryStage.FULL_ROLLOUT,
        )
        results = eng.list_canaries(stage=CanaryStage.BASELINE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_comparison
# -------------------------------------------------------------------


class TestAddComparison:
    def test_basic(self):
        eng = _engine()
        c = eng.add_comparison(
            "dep-001",
            metric=CanaryMetric.ERROR_RATE,
            baseline_value=1.0,
            canary_value=1.5,
            deviation_pct=50.0,
        )
        assert c.deployment_id == "dep-001"
        assert c.baseline_value == 1.0
        assert c.canary_value == 1.5
        assert c.deviation_pct == 50.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_comparison(f"dep-{i}")
        assert len(eng._comparisons) == 2


# -------------------------------------------------------------------
# analyze_canary_success_rate
# -------------------------------------------------------------------


class TestAnalyzeCanarySuccessRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_canary(
            "dep-1",
            "svc-a",
            verdict=CanaryVerdict.PROMOTE,
        )
        eng.record_canary(
            "dep-2",
            "svc-b",
            verdict=CanaryVerdict.ROLLBACK,
        )
        result = eng.analyze_canary_success_rate()
        assert result["total"] == 2
        assert result["promoted"] == 1
        assert result["rolled_back"] == 1
        assert result["success_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_canary_success_rate()
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failed_canaries
# -------------------------------------------------------------------


class TestIdentifyFailedCanaries:
    def test_with_failures(self):
        eng = _engine(min_canary_score=80.0)
        eng.record_canary(
            "dep-1",
            "svc-a",
            canary_score=50.0,
        )
        eng.record_canary(
            "dep-2",
            "svc-b",
            canary_score=95.0,
        )
        results = eng.identify_failed_canaries()
        assert len(results) == 1
        assert results[0]["canary_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_canaries() == []


# -------------------------------------------------------------------
# rank_by_canary_score
# -------------------------------------------------------------------


class TestRankByCanaryScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_canary(
            "dep-1",
            "svc-a",
            canary_score=60.0,
        )
        eng.record_canary(
            "dep-2",
            "svc-b",
            canary_score=95.0,
        )
        results = eng.rank_by_canary_score()
        assert results[0]["avg_canary_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_canary_score() == []


# -------------------------------------------------------------------
# detect_canary_trends
# -------------------------------------------------------------------


class TestDetectCanaryTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(4):
            eng.record_canary("dep-x", "svc-trending")
        eng.record_canary("dep-y", "svc-stable")
        results = eng.detect_canary_trends()
        assert len(results) == 1
        assert results[0]["service"] == "svc-trending"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_canary_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_canary_score=80.0)
        eng.record_canary(
            "dep-1",
            "svc-a",
            canary_score=50.0,
            verdict=CanaryVerdict.ROLLBACK,
        )
        eng.record_canary(
            "dep-2",
            "svc-b",
            canary_score=95.0,
            verdict=CanaryVerdict.PROMOTE,
        )
        eng.add_comparison("dep-1")
        report = eng.generate_report()
        assert isinstance(report, CanaryScorerReport)
        assert report.total_records == 2
        assert report.total_comparisons == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable limits" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_canary("dep-1", "svc-a")
        eng.add_comparison("dep-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._comparisons) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_comparisons"] == 0
        assert stats["verdict_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_canary(
            "dep-1",
            "svc-a",
            verdict=CanaryVerdict.PROMOTE,
        )
        eng.record_canary(
            "dep-2",
            "svc-b",
            verdict=CanaryVerdict.ROLLBACK,
        )
        eng.add_comparison("dep-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_comparisons"] == 1
        assert stats["unique_services"] == 2

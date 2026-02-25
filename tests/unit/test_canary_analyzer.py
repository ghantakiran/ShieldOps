"""Tests for shieldops.changes.canary_analyzer — DeploymentCanaryAnalyzer."""

from __future__ import annotations

from shieldops.changes.canary_analyzer import (
    CanaryAnalysis,
    CanaryComparison,
    CanaryDecision,
    CanaryMetricType,
    CanaryPhase,
    CanaryReport,
    DeploymentCanaryAnalyzer,
)


def _engine(**kw) -> DeploymentCanaryAnalyzer:
    return DeploymentCanaryAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CanaryDecision (5)
    def test_decision_promote(self):
        assert CanaryDecision.PROMOTE == "promote"

    def test_decision_rollback(self):
        assert CanaryDecision.ROLLBACK == "rollback"

    def test_decision_extend(self):
        assert CanaryDecision.EXTEND == "extend"

    def test_decision_pause(self):
        assert CanaryDecision.PAUSE == "pause"

    def test_decision_manual(self):
        assert CanaryDecision.MANUAL_REVIEW == "manual_review"

    # CanaryMetricType (5)
    def test_metric_error_rate(self):
        assert CanaryMetricType.ERROR_RATE == "error_rate"

    def test_metric_latency(self):
        assert CanaryMetricType.LATENCY_P99 == "latency_p99"

    def test_metric_success(self):
        assert CanaryMetricType.SUCCESS_RATE == "success_rate"

    def test_metric_throughput(self):
        assert CanaryMetricType.THROUGHPUT == "throughput"

    def test_metric_saturation(self):
        assert CanaryMetricType.SATURATION == "saturation"

    # CanaryPhase (5)
    def test_phase_initializing(self):
        assert CanaryPhase.INITIALIZING == "initializing"

    def test_phase_traffic_shifting(self):
        assert CanaryPhase.TRAFFIC_SHIFTING == "traffic_shifting"

    def test_phase_observing(self):
        assert CanaryPhase.OBSERVING == "observing"

    def test_phase_deciding(self):
        assert CanaryPhase.DECIDING == "deciding"

    def test_phase_completed(self):
        assert CanaryPhase.COMPLETED == "completed"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_analysis_defaults(self):
        r = CanaryAnalysis()
        assert r.id
        assert r.deployment_id == ""
        assert r.service_name == ""
        assert r.canary_version == ""
        assert r.baseline_version == ""
        assert r.phase == CanaryPhase.INITIALIZING
        assert r.decision == CanaryDecision.MANUAL_REVIEW
        assert r.traffic_pct == 0.0
        assert r.canary_metrics == {}
        assert r.baseline_metrics == {}
        assert r.deviation_pct == 0.0
        assert r.created_at > 0

    def test_comparison_defaults(self):
        r = CanaryComparison()
        assert r.id
        assert r.analysis_id == ""
        assert r.metric_type == CanaryMetricType.ERROR_RATE
        assert r.canary_value == 0.0
        assert r.baseline_value == 0.0
        assert r.deviation_pct == 0.0
        assert r.within_threshold is True
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CanaryReport()
        assert r.total_analyses == 0
        assert r.promotion_rate_pct == 0.0
        assert r.rollback_rate_pct == 0.0
        assert r.by_decision == {}
        assert r.by_phase == {}
        assert r.flaky_services == []
        assert r.avg_deviation_pct == 0.0
        assert r.recommendations == []


# -------------------------------------------------------------------
# create_analysis
# -------------------------------------------------------------------


class TestCreateAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.create_analysis("dep-001", "api-svc", "v2.1", "v2.0")
        assert a.deployment_id == "dep-001"
        assert a.service_name == "api-svc"
        assert a.canary_version == "v2.1"
        assert a.baseline_version == "v2.0"

    def test_with_traffic_pct(self):
        eng = _engine()
        a = eng.create_analysis("dep-002", "api-svc", "v2.1", "v2.0", traffic_pct=15.0)
        assert a.traffic_pct == 15.0

    def test_unique_ids(self):
        eng = _engine()
        a1 = eng.create_analysis("dep-001", "svc-a", "v1", "v0")
        a2 = eng.create_analysis("dep-002", "svc-b", "v1", "v0")
        assert a1.id != a2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.create_analysis(f"dep-{i}", "svc", f"v{i}", "v0")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_analysis
# -------------------------------------------------------------------


class TestGetAnalysis:
    def test_found(self):
        eng = _engine()
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        assert eng.get_analysis(a.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_analysis("nonexistent") is None


# -------------------------------------------------------------------
# list_analyses
# -------------------------------------------------------------------


class TestListAnalyses:
    def test_list_all(self):
        eng = _engine()
        eng.create_analysis("dep-001", "svc-a", "v2", "v1")
        eng.create_analysis("dep-002", "svc-b", "v3", "v2")
        assert len(eng.list_analyses()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.create_analysis("dep-001", "svc-a", "v2", "v1")
        eng.create_analysis("dep-002", "svc-b", "v3", "v2")
        results = eng.list_analyses(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_decision(self):
        eng = _engine()
        a = eng.create_analysis("dep-001", "svc-a", "v2", "v1")
        eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
        eng.decide_promotion(a.id)
        eng.create_analysis("dep-002", "svc-b", "v3", "v2")  # default MANUAL_REVIEW
        results = eng.list_analyses(decision=CanaryDecision.PROMOTE)
        assert len(results) == 1


# -------------------------------------------------------------------
# compare_metrics
# -------------------------------------------------------------------


class TestCompareMetrics:
    def test_within_threshold(self):
        eng = _engine(deviation_threshold_pct=10.0)
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        # deviation = |100-105|/105*100 = 4.76% < 10%
        comp = eng.compare_metrics(a.id, CanaryMetricType.LATENCY_P99, 100.0, 105.0)
        assert comp.within_threshold is True
        assert comp.deviation_pct < 10.0

    def test_high_deviation(self):
        eng = _engine(deviation_threshold_pct=10.0)
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        # deviation = |150-100|/100*100 = 50% > 10%
        comp = eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 150.0, 100.0)
        assert comp.within_threshold is False
        assert comp.deviation_pct == 50.0


# -------------------------------------------------------------------
# decide_promotion
# -------------------------------------------------------------------


class TestDecidePromotion:
    def test_all_good_promote(self):
        eng = _engine(deviation_threshold_pct=10.0)
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        # Small deviations: all within 10%
        eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.05)
        eng.compare_metrics(a.id, CanaryMetricType.LATENCY_P99, 200.0, 195.0)
        eng.compare_metrics(a.id, CanaryMetricType.SUCCESS_RATE, 99.5, 99.8)
        result = eng.decide_promotion(a.id)
        assert result["decision"] == "promote"
        assert result["reason"] == "all_metrics_within_threshold"

    def test_slight_deviation_extend(self):
        eng = _engine(deviation_threshold_pct=10.0)
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        # One metric slightly above threshold (15% > 10%) but below 2x (< 20%)
        eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
        eng.compare_metrics(a.id, CanaryMetricType.LATENCY_P99, 115.0, 100.0)
        result = eng.decide_promotion(a.id)
        assert result["decision"] == "extend"

    def test_large_deviation_rollback(self):
        eng = _engine(deviation_threshold_pct=10.0)
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        # Deviation > 2x threshold (>20%): 25% deviation
        eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 125.0, 100.0)
        result = eng.decide_promotion(a.id)
        assert result["decision"] == "rollback"
        assert result["reason"] == "severe_deviation_detected"


# -------------------------------------------------------------------
# advance_phase
# -------------------------------------------------------------------


class TestAdvancePhase:
    def test_valid(self):
        eng = _engine()
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        result = eng.advance_phase(a.id, CanaryPhase.OBSERVING)
        assert result["old_phase"] == "initializing"
        assert result["new_phase"] == "observing"

    def test_not_found(self):
        eng = _engine()
        result = eng.advance_phase("bad-id", CanaryPhase.COMPLETED)
        assert result["error"] == "analysis_not_found"


# -------------------------------------------------------------------
# calculate_promotion_rate
# -------------------------------------------------------------------


class TestCalculatePromotionRate:
    def test_with_promotions(self):
        eng = _engine(deviation_threshold_pct=10.0)
        # Two analyses: one promoted, one rolled back
        a1 = eng.create_analysis("dep-001", "svc-a", "v2", "v1")
        eng.compare_metrics(a1.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
        eng.decide_promotion(a1.id)  # PROMOTE

        a2 = eng.create_analysis("dep-002", "svc-b", "v3", "v2")
        eng.compare_metrics(a2.id, CanaryMetricType.ERROR_RATE, 150.0, 100.0)
        eng.decide_promotion(a2.id)  # ROLLBACK (50% > 20%)

        result = eng.calculate_promotion_rate()
        assert result["promotion_rate_pct"] == 50.0
        assert result["rollback_rate_pct"] == 50.0
        assert result["total"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_promotion_rate()
        assert result["promotion_rate_pct"] == 0.0
        assert result["total"] == 0


# -------------------------------------------------------------------
# identify_flaky_services
# -------------------------------------------------------------------


class TestIdentifyFlakyServices:
    def test_flaky_exists(self):
        eng = _engine(deviation_threshold_pct=10.0)
        # Create 3 analyses for same service, 2 with rollbacks (>30% rate)
        for i in range(3):
            a = eng.create_analysis(f"dep-{i}", "flaky-svc", f"v{i}", "v0")
            if i < 2:
                # Force rollback: >20% deviation
                eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 130.0, 100.0)
            else:
                eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
            eng.decide_promotion(a.id)
        flaky = eng.identify_flaky_services()
        assert len(flaky) == 1
        assert flaky[0]["service_name"] == "flaky-svc"
        assert flaky[0]["rollback_rate_pct"] > 30.0

    def test_none_flaky(self):
        eng = _engine(deviation_threshold_pct=10.0)
        for i in range(3):
            a = eng.create_analysis(f"dep-{i}", "stable-svc", f"v{i}", "v0")
            eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
            eng.decide_promotion(a.id)
        flaky = eng.identify_flaky_services()
        assert len(flaky) == 0


# -------------------------------------------------------------------
# generate_canary_report
# -------------------------------------------------------------------


class TestGenerateCanaryReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_canary_report()
        assert report.total_analyses == 0
        assert report.promotion_rate_pct == 0.0

    def test_with_data(self):
        eng = _engine(deviation_threshold_pct=10.0)
        a1 = eng.create_analysis("dep-001", "svc-a", "v2", "v1")
        eng.compare_metrics(a1.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
        eng.decide_promotion(a1.id)

        a2 = eng.create_analysis("dep-002", "svc-b", "v3", "v2")
        eng.compare_metrics(a2.id, CanaryMetricType.ERROR_RATE, 150.0, 100.0)
        eng.decide_promotion(a2.id)

        report = eng.generate_canary_report()
        assert report.total_analyses == 2
        assert report.by_decision != {}
        assert report.recommendations != []


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        a = eng.create_analysis("dep-001", "svc", "v2", "v1")
        eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._comparisons) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_analyses"] == 0
        assert stats["total_comparisons"] == 0

    def test_populated(self):
        eng = _engine()
        a = eng.create_analysis("dep-001", "svc-a", "v2", "v1")
        eng.compare_metrics(a.id, CanaryMetricType.ERROR_RATE, 1.0, 1.0)
        eng.compare_metrics(a.id, CanaryMetricType.LATENCY_P99, 200.0, 190.0)
        stats = eng.get_stats()
        assert stats["total_analyses"] == 1
        assert stats["total_comparisons"] == 2
        assert stats["unique_services"] == 1

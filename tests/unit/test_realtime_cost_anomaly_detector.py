"""Tests for shieldops.billing.realtime_cost_anomaly_detector."""

from __future__ import annotations

from shieldops.billing.realtime_cost_anomaly_detector import (
    AnomalyAnalysis,
    AnomalyType,
    CostAnomalyRecord,
    CostAnomalyReport,
    CostSource,
    DetectionMethod,
    RealtimeCostAnomalyDetector,
)


def _engine(**kw) -> RealtimeCostAnomalyDetector:
    return RealtimeCostAnomalyDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_anomalytype_spike(self):
        assert AnomalyType.SPIKE == "spike"

    def test_anomalytype_drift(self):
        assert AnomalyType.DRIFT == "drift"

    def test_anomalytype_seasonal(self):
        assert AnomalyType.SEASONAL == "seasonal"

    def test_anomalytype_structural(self):
        assert AnomalyType.STRUCTURAL == "structural"

    def test_anomalytype_unknown(self):
        assert AnomalyType.UNKNOWN == "unknown"

    def test_costsource_compute(self):
        assert CostSource.COMPUTE == "compute"

    def test_costsource_storage(self):
        assert CostSource.STORAGE == "storage"

    def test_costsource_network(self):
        assert CostSource.NETWORK == "network"

    def test_costsource_database(self):
        assert CostSource.DATABASE == "database"

    def test_costsource_services(self):
        assert CostSource.SERVICES == "services"

    def test_detectionmethod_statistical(self):
        assert DetectionMethod.STATISTICAL == "statistical"

    def test_detectionmethod_ml_based(self):
        assert DetectionMethod.ML_BASED == "ml_based"

    def test_detectionmethod_rule_based(self):
        assert DetectionMethod.RULE_BASED == "rule_based"

    def test_detectionmethod_hybrid(self):
        assert DetectionMethod.HYBRID == "hybrid"

    def test_detectionmethod_manual(self):
        assert DetectionMethod.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_anomaly_record_defaults(self):
        r = CostAnomalyRecord()
        assert r.id
        assert r.anomaly_type == AnomalyType.UNKNOWN
        assert r.cost_source == CostSource.COMPUTE
        assert r.detection_method == DetectionMethod.STATISTICAL
        assert r.amount == 0.0
        assert r.baseline == 0.0
        assert r.deviation_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_anomaly_analysis_defaults(self):
        a = AnomalyAnalysis()
        assert a.id
        assert a.anomaly_type == AnomalyType.UNKNOWN
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_cost_anomaly_report_defaults(self):
        r = CostAnomalyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.anomaly_count == 0
        assert r.avg_deviation_pct == 0.0
        assert r.by_anomaly_type == {}
        assert r.by_cost_source == {}
        assert r.by_detection_method == {}
        assert r.top_anomalies == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_anomaly
# ---------------------------------------------------------------------------


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        r = eng.record_anomaly(
            anomaly_type=AnomalyType.SPIKE,
            cost_source=CostSource.COMPUTE,
            detection_method=DetectionMethod.ML_BASED,
            amount=1500.0,
            baseline=500.0,
            deviation_pct=200.0,
            service="ec2",
            team="platform",
        )
        assert r.anomaly_type == AnomalyType.SPIKE
        assert r.cost_source == CostSource.COMPUTE
        assert r.detection_method == DetectionMethod.ML_BASED
        assert r.amount == 1500.0
        assert r.deviation_pct == 200.0
        assert r.service == "ec2"
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_anomaly(anomaly_type=AnomalyType.DRIFT)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_anomaly
# ---------------------------------------------------------------------------


class TestGetAnomaly:
    def test_found(self):
        eng = _engine()
        r = eng.record_anomaly(
            anomaly_type=AnomalyType.SPIKE,
            cost_source=CostSource.STORAGE,
        )
        result = eng.get_anomaly(r.id)
        assert result is not None
        assert result.cost_source == CostSource.STORAGE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly(anomaly_type=AnomalyType.SPIKE)
        eng.record_anomaly(anomaly_type=AnomalyType.DRIFT)
        assert len(eng.list_anomalies()) == 2

    def test_filter_by_anomaly_type(self):
        eng = _engine()
        eng.record_anomaly(anomaly_type=AnomalyType.SPIKE)
        eng.record_anomaly(anomaly_type=AnomalyType.DRIFT)
        results = eng.list_anomalies(anomaly_type=AnomalyType.SPIKE)
        assert len(results) == 1

    def test_filter_by_cost_source(self):
        eng = _engine()
        eng.record_anomaly(cost_source=CostSource.COMPUTE)
        eng.record_anomaly(cost_source=CostSource.STORAGE)
        results = eng.list_anomalies(cost_source=CostSource.COMPUTE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_anomaly(team="security")
        eng.record_anomaly(team="platform")
        results = eng.list_anomalies(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_anomaly(anomaly_type=AnomalyType.SPIKE)
        assert len(eng.list_anomalies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            anomaly_type=AnomalyType.STRUCTURAL,
            analysis_score=85.0,
            threshold=70.0,
            breached=True,
            description="cost spike detected",
        )
        assert a.anomaly_type == AnomalyType.STRUCTURAL
        assert a.analysis_score == 85.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(anomaly_type=AnomalyType.SPIKE)
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_source_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeSourceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_anomaly(cost_source=CostSource.COMPUTE, deviation_pct=50.0)
        eng.record_anomaly(cost_source=CostSource.COMPUTE, deviation_pct=30.0)
        result = eng.analyze_source_distribution()
        assert "compute" in result
        assert result["compute"]["count"] == 2
        assert result["compute"]["avg_deviation_pct"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_source_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_deviation_anomalies
# ---------------------------------------------------------------------------


class TestIdentifyHighDeviationAnomalies:
    def test_detects_above_threshold(self):
        eng = _engine(deviation_threshold=30.0)
        eng.record_anomaly(anomaly_type=AnomalyType.SPIKE, deviation_pct=50.0)
        eng.record_anomaly(anomaly_type=AnomalyType.DRIFT, deviation_pct=10.0)
        results = eng.identify_high_deviation_anomalies()
        assert len(results) == 1
        assert results[0]["deviation_pct"] == 50.0

    def test_sorted_descending(self):
        eng = _engine(deviation_threshold=10.0)
        eng.record_anomaly(deviation_pct=80.0)
        eng.record_anomaly(deviation_pct=40.0)
        results = eng.identify_high_deviation_anomalies()
        assert results[0]["deviation_pct"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_deviation_anomalies() == []


# ---------------------------------------------------------------------------
# rank_by_impact
# ---------------------------------------------------------------------------


class TestRankByImpact:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_anomaly(service="ec2", amount=1000.0)
        eng.record_anomaly(service="s3", amount=200.0)
        results = eng.rank_by_impact()
        assert results[0]["service"] == "ec2"
        assert results[0]["total_amount"] == 1000.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# ---------------------------------------------------------------------------
# detect_anomaly_trends
# ---------------------------------------------------------------------------


class TestDetectAnomalyTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(anomaly_type=AnomalyType.SPIKE, analysis_score=50.0)
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "worsening"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(deviation_threshold=30.0)
        eng.record_anomaly(
            anomaly_type=AnomalyType.SPIKE,
            cost_source=CostSource.COMPUTE,
            detection_method=DetectionMethod.ML_BASED,
            deviation_pct=50.0,
            amount=1000.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CostAnomalyReport)
        assert report.total_records == 1
        assert report.anomaly_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_anomaly(anomaly_type=AnomalyType.SPIKE)
        eng.add_analysis(anomaly_type=AnomalyType.SPIKE)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["anomaly_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_anomaly(
            anomaly_type=AnomalyType.SPIKE,
            service="ec2",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "spike" in stats["anomaly_type_distribution"]

"""Tests for shieldops.observability.metric_anomaly_classifier — MetricAnomalyClassifier."""

from __future__ import annotations

from shieldops.observability.metric_anomaly_classifier import (
    AnomalyConfidence,
    AnomalyImpact,
    AnomalyRecord,
    AnomalyType,
    ClassificationResult,
    MetricAnomalyClassifier,
    MetricAnomalyReport,
)


def _engine(**kw) -> MetricAnomalyClassifier:
    return MetricAnomalyClassifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_spike(self):
        assert AnomalyType.SPIKE == "spike"

    def test_type_drift(self):
        assert AnomalyType.DRIFT == "drift"

    def test_type_seasonal_deviation(self):
        assert AnomalyType.SEASONAL_DEVIATION == "seasonal_deviation"

    def test_type_noise(self):
        assert AnomalyType.NOISE == "noise"

    def test_type_step_change(self):
        assert AnomalyType.STEP_CHANGE == "step_change"

    def test_confidence_very_high(self):
        assert AnomalyConfidence.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert AnomalyConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert AnomalyConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert AnomalyConfidence.LOW == "low"

    def test_confidence_uncertain(self):
        assert AnomalyConfidence.UNCERTAIN == "uncertain"

    def test_impact_critical(self):
        assert AnomalyImpact.CRITICAL == "critical"

    def test_impact_significant(self):
        assert AnomalyImpact.SIGNIFICANT == "significant"

    def test_impact_moderate(self):
        assert AnomalyImpact.MODERATE == "moderate"

    def test_impact_minor(self):
        assert AnomalyImpact.MINOR == "minor"

    def test_impact_negligible(self):
        assert AnomalyImpact.NEGLIGIBLE == "negligible"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_anomaly_record_defaults(self):
        r = AnomalyRecord()
        assert r.id
        assert r.metric_name == ""
        assert r.anomaly_type == AnomalyType.SPIKE
        assert r.anomaly_confidence == AnomalyConfidence.VERY_HIGH
        assert r.anomaly_impact == AnomalyImpact.CRITICAL
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_classification_result_defaults(self):
        c = ClassificationResult()
        assert c.id
        assert c.metric_name == ""
        assert c.anomaly_type == AnomalyType.SPIKE
        assert c.classification_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_metric_anomaly_report_defaults(self):
        r = MetricAnomalyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_classifications == 0
        assert r.low_confidence_count == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_type == {}
        assert r.by_confidence == {}
        assert r.by_impact == {}
        assert r.top_low_confidence == []
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
            metric_name="cpu_usage",
            anomaly_type=AnomalyType.DRIFT,
            anomaly_confidence=AnomalyConfidence.HIGH,
            anomaly_impact=AnomalyImpact.SIGNIFICANT,
            confidence_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.metric_name == "cpu_usage"
        assert r.anomaly_type == AnomalyType.DRIFT
        assert r.anomaly_confidence == AnomalyConfidence.HIGH
        assert r.anomaly_impact == AnomalyImpact.SIGNIFICANT
        assert r.confidence_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_anomaly(metric_name=f"metric-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_anomaly
# ---------------------------------------------------------------------------


class TestGetAnomaly:
    def test_found(self):
        eng = _engine()
        r = eng.record_anomaly(
            metric_name="cpu_usage",
            anomaly_type=AnomalyType.STEP_CHANGE,
        )
        result = eng.get_anomaly(r.id)
        assert result is not None
        assert result.anomaly_type == AnomalyType.STEP_CHANGE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly(metric_name="metric-1")
        eng.record_anomaly(metric_name="metric-2")
        assert len(eng.list_anomalies()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_anomaly(
            metric_name="metric-1",
            anomaly_type=AnomalyType.SPIKE,
        )
        eng.record_anomaly(
            metric_name="metric-2",
            anomaly_type=AnomalyType.DRIFT,
        )
        results = eng.list_anomalies(
            anomaly_type=AnomalyType.SPIKE,
        )
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_anomaly(
            metric_name="metric-1",
            anomaly_confidence=AnomalyConfidence.HIGH,
        )
        eng.record_anomaly(
            metric_name="metric-2",
            anomaly_confidence=AnomalyConfidence.LOW,
        )
        results = eng.list_anomalies(
            anomaly_confidence=AnomalyConfidence.HIGH,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_anomaly(metric_name="metric-1", team="sre")
        eng.record_anomaly(metric_name="metric-2", team="platform")
        results = eng.list_anomalies(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_anomaly(metric_name=f"metric-{i}")
        assert len(eng.list_anomalies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_classification
# ---------------------------------------------------------------------------


class TestAddClassification:
    def test_basic(self):
        eng = _engine()
        c = eng.add_classification(
            metric_name="cpu_usage",
            anomaly_type=AnomalyType.DRIFT,
            classification_score=55.0,
            threshold=75.0,
            breached=True,
            description="Low confidence classification",
        )
        assert c.metric_name == "cpu_usage"
        assert c.anomaly_type == AnomalyType.DRIFT
        assert c.classification_score == 55.0
        assert c.threshold == 75.0
        assert c.breached is True
        assert c.description == "Low confidence classification"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_classification(metric_name=f"metric-{i}")
        assert len(eng._classifications) == 2


# ---------------------------------------------------------------------------
# analyze_anomaly_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeAnomalyDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_anomaly(
            metric_name="metric-1",
            anomaly_type=AnomalyType.SPIKE,
            confidence_score=80.0,
        )
        eng.record_anomaly(
            metric_name="metric-2",
            anomaly_type=AnomalyType.SPIKE,
            confidence_score=60.0,
        )
        result = eng.analyze_anomaly_distribution()
        assert "spike" in result
        assert result["spike"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_anomaly_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_anomalies
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidenceAnomalies:
    def test_detects(self):
        eng = _engine(confidence_threshold=75.0)
        eng.record_anomaly(
            metric_name="metric-low",
            confidence_score=40.0,
        )
        eng.record_anomaly(
            metric_name="metric-high",
            confidence_score=90.0,
        )
        results = eng.identify_low_confidence_anomalies()
        assert len(results) == 1
        assert results[0]["metric_name"] == "metric-low"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_anomalies() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_ranked(self):
        eng = _engine()
        eng.record_anomaly(
            metric_name="metric-1",
            service="api-gateway",
            confidence_score=90.0,
        )
        eng.record_anomaly(
            metric_name="metric-2",
            service="payments",
            confidence_score=30.0,
        )
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_confidence_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_anomaly_trends
# ---------------------------------------------------------------------------


class TestDetectAnomalyTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_classification(
                metric_name="metric-1",
                classification_score=50.0,
            )
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_classification(metric_name="metric-1", classification_score=30.0)
        eng.add_classification(metric_name="metric-2", classification_score=30.0)
        eng.add_classification(metric_name="metric-3", classification_score=80.0)
        eng.add_classification(metric_name="metric-4", classification_score=80.0)
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_anomaly_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(confidence_threshold=75.0)
        eng.record_anomaly(
            metric_name="cpu_usage",
            anomaly_type=AnomalyType.SPIKE,
            anomaly_confidence=AnomalyConfidence.LOW,
            anomaly_impact=AnomalyImpact.CRITICAL,
            confidence_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, MetricAnomalyReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_low_confidence) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_anomaly(metric_name="metric-1")
        eng.add_classification(metric_name="metric-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._classifications) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_classifications"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_anomaly(
            metric_name="cpu_usage",
            anomaly_type=AnomalyType.SPIKE,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "spike" in stats["type_distribution"]

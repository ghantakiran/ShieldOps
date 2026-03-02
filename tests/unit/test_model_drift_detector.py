"""Tests for shieldops.analytics.model_drift_detector — ModelDriftDetector."""

from __future__ import annotations

from shieldops.analytics.model_drift_detector import (
    DetectionMethod,
    DriftAnalysis,
    DriftRecord,
    DriftReport,
    DriftSeverity,
    DriftType,
    ModelDriftDetector,
)


def _engine(**kw) -> ModelDriftDetector:
    return ModelDriftDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_drift_type_data(self):
        assert DriftType.DATA == "data"

    def test_drift_type_concept(self):
        assert DriftType.CONCEPT == "concept"

    def test_drift_type_prediction(self):
        assert DriftType.PREDICTION == "prediction"

    def test_drift_type_feature(self):
        assert DriftType.FEATURE == "feature"

    def test_drift_type_performance(self):
        assert DriftType.PERFORMANCE == "performance"

    def test_severity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert DriftSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert DriftSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert DriftSeverity.LOW == "low"

    def test_severity_none(self):
        assert DriftSeverity.NONE == "none"

    def test_method_ks_test(self):
        assert DetectionMethod.KS_TEST == "ks_test"

    def test_method_psi(self):
        assert DetectionMethod.PSI == "psi"

    def test_method_wasserstein(self):
        assert DetectionMethod.WASSERSTEIN == "wasserstein"

    def test_method_chi_square(self):
        assert DetectionMethod.CHI_SQUARE == "chi_square"

    def test_method_adwin(self):
        assert DetectionMethod.ADWIN == "adwin"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_drift_record_defaults(self):
        r = DriftRecord()
        assert r.id
        assert r.model_id == ""
        assert r.drift_type == DriftType.DATA
        assert r.drift_severity == DriftSeverity.LOW
        assert r.detection_method == DetectionMethod.KS_TEST
        assert r.drift_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_drift_analysis_defaults(self):
        a = DriftAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.drift_type == DriftType.DATA
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_drift_report_defaults(self):
        r = DriftReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.severe_count == 0
        assert r.avg_drift_score == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_method == {}
        assert r.top_drifting == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_init(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._drift_threshold == 0.05
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_custom_init(self):
        eng = _engine(max_records=500, drift_threshold=0.1)
        assert eng._max_records == 500
        assert eng._drift_threshold == 0.1

    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0


# ---------------------------------------------------------------------------
# record_drift / get_drift
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_drift(
            model_id="model-001",
            drift_type=DriftType.CONCEPT,
            drift_severity=DriftSeverity.HIGH,
            detection_method=DetectionMethod.PSI,
            drift_score=0.15,
            feature_name="age",
            service="credit-svc",
            team="ml-team",
        )
        assert r.model_id == "model-001"
        assert r.drift_type == DriftType.CONCEPT
        assert r.drift_severity == DriftSeverity.HIGH
        assert r.drift_score == 0.15
        assert r.feature_name == "age"
        assert r.service == "credit-svc"
        assert r.team == "ml-team"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_drift(model_id="m-001", drift_score=0.2)
        result = eng.get_drift(r.id)
        assert result is not None
        assert result.model_id == "m-001"

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_drift("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_drifts
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_drift(model_id="m-001")
        eng.record_drift(model_id="m-002")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_drift_type(self):
        eng = _engine()
        eng.record_drift(model_id="m-001", drift_type=DriftType.DATA)
        eng.record_drift(model_id="m-002", drift_type=DriftType.CONCEPT)
        results = eng.list_drifts(drift_type=DriftType.DATA)
        assert len(results) == 1
        assert results[0].model_id == "m-001"

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_drift(model_id="m-001", drift_severity=DriftSeverity.HIGH)
        eng.record_drift(model_id="m-002", drift_severity=DriftSeverity.LOW)
        results = eng.list_drifts(drift_severity=DriftSeverity.HIGH)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_drift(model_id="m-001", team="ml-team")
        eng.record_drift(model_id="m-002", team="data-team")
        results = eng.list_drifts(team="ml-team")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_drift(model_id=f"m-{i}")
        assert len(eng.list_drifts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            drift_type=DriftType.CONCEPT,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="drift detected",
        )
        assert a.model_id == "m-001"
        assert a.drift_type == DriftType.CONCEPT
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.drift_type == DriftType.DATA
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift(model_id="m-001", drift_type=DriftType.DATA, drift_score=0.1)
        eng.record_drift(model_id="m-002", drift_type=DriftType.DATA, drift_score=0.2)
        result = eng.analyze_distribution()
        assert "data" in result
        assert result["data"]["count"] == 2
        assert result["data"]["avg_drift_score"] == 0.15

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(drift_threshold=0.1)
        eng.record_drift(model_id="m-001", drift_score=0.2)
        eng.record_drift(model_id="m-002", drift_score=0.05)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_descending(self):
        eng = _engine(drift_threshold=0.05)
        eng.record_drift(model_id="m-001", drift_score=0.15)
        eng.record_drift(model_id="m-002", drift_score=0.30)
        results = eng.identify_severe_drifts()
        assert len(results) == 2
        assert results[0]["drift_score"] == 0.30

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_drift(model_id="m-001", drift_score=0.9)
        eng.record_drift(model_id="m-002", drift_score=0.3)
        results = eng.rank_by_severity()
        assert len(results) == 2
        assert results[0]["model_id"] == "m-001"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(model_id="m-001", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(model_id="m-001", analysis_score=20.0)
        eng.add_analysis(model_id="m-002", analysis_score=20.0)
        eng.add_analysis(model_id="m-003", analysis_score=80.0)
        eng.add_analysis(model_id="m-004", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "worsening"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(drift_threshold=0.1)
        eng.record_drift(
            model_id="m-001",
            drift_type=DriftType.DATA,
            drift_severity=DriftSeverity.HIGH,
            detection_method=DetectionMethod.KS_TEST,
            drift_score=0.2,
        )
        report = eng.generate_report()
        assert isinstance(report, DriftReport)
        assert report.total_records == 1
        assert report.severe_count == 1
        assert len(report.top_drifting) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_drift(model_id="m-001")
        eng.add_analysis(model_id="m-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_drift(
            model_id="m-001",
            drift_type=DriftType.DATA,
            service="credit-svc",
            team="ml-team",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_models"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"

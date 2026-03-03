"""Tests for shieldops.analytics.feature_drift_monitor — FeatureDriftMonitor."""

from __future__ import annotations

from shieldops.analytics.feature_drift_monitor import (
    DriftSource,
    DriftStatus,
    FeatureDriftAnalysis,
    FeatureDriftMonitor,
    FeatureDriftRecord,
    FeatureDriftReport,
    FeatureType,
)


def _engine(**kw) -> FeatureDriftMonitor:
    return FeatureDriftMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_feature_type_numeric(self):
        assert FeatureType.NUMERIC == "numeric"

    def test_feature_type_categorical(self):
        assert FeatureType.CATEGORICAL == "categorical"

    def test_feature_type_boolean(self):
        assert FeatureType.BOOLEAN == "boolean"

    def test_feature_type_text(self):
        assert FeatureType.TEXT == "text"

    def test_feature_type_embedding(self):
        assert FeatureType.EMBEDDING == "embedding"

    def test_drift_source_upstream(self):
        assert DriftSource.UPSTREAM == "upstream"

    def test_drift_source_pipeline(self):
        assert DriftSource.PIPELINE == "pipeline"

    def test_drift_source_schema(self):
        assert DriftSource.SCHEMA == "schema"

    def test_drift_source_seasonal(self):
        assert DriftSource.SEASONAL == "seasonal"

    def test_drift_source_unknown(self):
        assert DriftSource.UNKNOWN == "unknown"

    def test_drift_status_detected(self):
        assert DriftStatus.DETECTED == "detected"

    def test_drift_status_monitoring(self):
        assert DriftStatus.MONITORING == "monitoring"

    def test_drift_status_resolved(self):
        assert DriftStatus.RESOLVED == "resolved"

    def test_drift_status_ignored(self):
        assert DriftStatus.IGNORED == "ignored"

    def test_drift_status_escalated(self):
        assert DriftStatus.ESCALATED == "escalated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_feature_drift_record_defaults(self):
        r = FeatureDriftRecord()
        assert r.id
        assert r.feature_name == ""
        assert r.model_id == ""
        assert r.feature_type == FeatureType.NUMERIC
        assert r.drift_source == DriftSource.UNKNOWN
        assert r.drift_status == DriftStatus.MONITORING
        assert r.drift_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_feature_drift_analysis_defaults(self):
        a = FeatureDriftAnalysis()
        assert a.id
        assert a.feature_name == ""
        assert a.feature_type == FeatureType.NUMERIC
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_feature_drift_report_defaults(self):
        r = FeatureDriftReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.drifted_count == 0
        assert r.avg_drift_score == 0.0
        assert r.by_type == {}
        assert r.by_source == {}
        assert r.by_status == {}
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
        assert eng._drift_threshold == 0.1
        assert len(eng._records) == 0

    def test_custom_init(self):
        eng = _engine(max_records=500, drift_threshold=0.2)
        assert eng._max_records == 500
        assert eng._drift_threshold == 0.2

    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0


# ---------------------------------------------------------------------------
# record_drift / get_drift
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_drift(
            feature_name="age",
            model_id="model-001",
            feature_type=FeatureType.NUMERIC,
            drift_source=DriftSource.UPSTREAM,
            drift_status=DriftStatus.DETECTED,
            drift_score=0.25,
            service="credit-svc",
            team="ml-team",
        )
        assert r.feature_name == "age"
        assert r.model_id == "model-001"
        assert r.feature_type == FeatureType.NUMERIC
        assert r.drift_score == 0.25

    def test_get_found(self):
        eng = _engine()
        r = eng.record_drift(feature_name="income", drift_score=0.3)
        result = eng.get_drift(r.id)
        assert result is not None
        assert result.feature_name == "income"

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_drift("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(feature_name=f"feat-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_drifts
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_drift(feature_name="age")
        eng.record_drift(feature_name="income")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_drift(feature_name="age", feature_type=FeatureType.NUMERIC)
        eng.record_drift(feature_name="cat", feature_type=FeatureType.CATEGORICAL)
        results = eng.list_drifts(feature_type=FeatureType.NUMERIC)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_drift(feature_name="age", drift_status=DriftStatus.DETECTED)
        eng.record_drift(feature_name="cat", drift_status=DriftStatus.RESOLVED)
        results = eng.list_drifts(drift_status=DriftStatus.DETECTED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_drift(feature_name="age", team="ml-team")
        eng.record_drift(feature_name="cat", team="data-team")
        results = eng.list_drifts(team="ml-team")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_drift(feature_name=f"feat-{i}")
        assert len(eng.list_drifts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            feature_name="age",
            feature_type=FeatureType.NUMERIC,
            analysis_score=85.0,
            threshold=70.0,
            breached=True,
            description="drift detected",
        )
        assert a.feature_name == "age"
        assert a.analysis_score == 85.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(feature_name=f"feat-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(feature_name="test")
        assert a.feature_type == FeatureType.NUMERIC
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift(feature_name="age", feature_type=FeatureType.NUMERIC, drift_score=0.1)
        eng.record_drift(feature_name="inc", feature_type=FeatureType.NUMERIC, drift_score=0.3)
        result = eng.analyze_distribution()
        assert "numeric" in result
        assert result["numeric"]["count"] == 2
        assert result["numeric"]["avg_drift_score"] == 0.2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(drift_threshold=0.1)
        eng.record_drift(feature_name="age", drift_score=0.25)
        eng.record_drift(feature_name="inc", drift_score=0.05)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["feature_name"] == "age"

    def test_sorted_descending(self):
        eng = _engine(drift_threshold=0.05)
        eng.record_drift(feature_name="age", drift_score=0.2)
        eng.record_drift(feature_name="inc", drift_score=0.4)
        results = eng.identify_severe_drifts()
        assert len(results) == 2
        assert results[0]["drift_score"] == 0.4

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_drift(feature_name="age", drift_score=0.9)
        eng.record_drift(feature_name="inc", drift_score=0.2)
        results = eng.rank_by_severity()
        assert len(results) == 2
        assert results[0]["feature_name"] == "age"

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
            eng.add_analysis(feature_name="age", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(feature_name="age", analysis_score=20.0)
        eng.add_analysis(feature_name="age", analysis_score=20.0)
        eng.add_analysis(feature_name="age", analysis_score=80.0)
        eng.add_analysis(feature_name="age", analysis_score=80.0)
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
            feature_name="age",
            feature_type=FeatureType.NUMERIC,
            drift_source=DriftSource.UPSTREAM,
            drift_status=DriftStatus.DETECTED,
            drift_score=0.25,
        )
        report = eng.generate_report()
        assert isinstance(report, FeatureDriftReport)
        assert report.total_records == 1
        assert report.drifted_count == 1
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
        eng.record_drift(feature_name="age")
        eng.add_analysis(feature_name="age")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_drift(feature_name="age", feature_type=FeatureType.NUMERIC, team="ml-team")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_features"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(feature_name=f"feat-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].feature_name == "feat-2"

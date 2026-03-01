"""Tests for shieldops.billing.cost_variance_analyzer — CostVarianceAnalyzer."""

from __future__ import annotations

from shieldops.billing.cost_variance_analyzer import (
    CostVarianceAnalyzer,
    CostVarianceReport,
    VarianceAnalysis,
    VarianceRecord,
    VarianceSeverity,
    VarianceSource,
    VarianceType,
)


def _engine(**kw) -> CostVarianceAnalyzer:
    return CostVarianceAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_favorable(self):
        assert VarianceType.FAVORABLE == "favorable"

    def test_type_unfavorable(self):
        assert VarianceType.UNFAVORABLE == "unfavorable"

    def test_type_neutral(self):
        assert VarianceType.NEUTRAL == "neutral"

    def test_type_spike(self):
        assert VarianceType.SPIKE == "spike"

    def test_type_seasonal(self):
        assert VarianceType.SEASONAL == "seasonal"

    def test_severity_critical(self):
        assert VarianceSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert VarianceSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert VarianceSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert VarianceSeverity.LOW == "low"

    def test_severity_negligible(self):
        assert VarianceSeverity.NEGLIGIBLE == "negligible"

    def test_source_compute(self):
        assert VarianceSource.COMPUTE == "compute"

    def test_source_storage(self):
        assert VarianceSource.STORAGE == "storage"

    def test_source_network(self):
        assert VarianceSource.NETWORK == "network"

    def test_source_licensing(self):
        assert VarianceSource.LICENSING == "licensing"

    def test_source_support(self):
        assert VarianceSource.SUPPORT == "support"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_variance_record_defaults(self):
        r = VarianceRecord()
        assert r.id
        assert r.variance_id == ""
        assert r.variance_type == VarianceType.NEUTRAL
        assert r.variance_severity == VarianceSeverity.NEGLIGIBLE
        assert r.variance_source == VarianceSource.COMPUTE
        assert r.variance_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_variance_analysis_defaults(self):
        a = VarianceAnalysis()
        assert a.id
        assert a.variance_id == ""
        assert a.variance_type == VarianceType.NEUTRAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = CostVarianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_variance_count == 0
        assert r.avg_variance_pct == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_source == {}
        assert r.top_variances == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_variance
# ---------------------------------------------------------------------------


class TestRecordVariance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_variance(
            variance_id="VAR-001",
            variance_type=VarianceType.UNFAVORABLE,
            variance_severity=VarianceSeverity.CRITICAL,
            variance_source=VarianceSource.COMPUTE,
            variance_pct=35.0,
            service="compute-cluster",
            team="infra",
        )
        assert r.variance_id == "VAR-001"
        assert r.variance_type == VarianceType.UNFAVORABLE
        assert r.variance_severity == VarianceSeverity.CRITICAL
        assert r.variance_source == VarianceSource.COMPUTE
        assert r.variance_pct == 35.0
        assert r.service == "compute-cluster"
        assert r.team == "infra"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_variance(variance_id=f"VAR-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_variance
# ---------------------------------------------------------------------------


class TestGetVariance:
    def test_found(self):
        eng = _engine()
        r = eng.record_variance(
            variance_id="VAR-001",
            variance_severity=VarianceSeverity.HIGH,
        )
        result = eng.get_variance(r.id)
        assert result is not None
        assert result.variance_severity == VarianceSeverity.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_variance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_variances
# ---------------------------------------------------------------------------


class TestListVariances:
    def test_list_all(self):
        eng = _engine()
        eng.record_variance(variance_id="VAR-001")
        eng.record_variance(variance_id="VAR-002")
        assert len(eng.list_variances()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_variance(
            variance_id="VAR-001",
            variance_type=VarianceType.FAVORABLE,
        )
        eng.record_variance(
            variance_id="VAR-002",
            variance_type=VarianceType.SPIKE,
        )
        results = eng.list_variances(
            variance_type=VarianceType.FAVORABLE,
        )
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_variance(
            variance_id="VAR-001",
            variance_severity=VarianceSeverity.CRITICAL,
        )
        eng.record_variance(
            variance_id="VAR-002",
            variance_severity=VarianceSeverity.LOW,
        )
        results = eng.list_variances(
            variance_severity=VarianceSeverity.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_variance(variance_id="VAR-001", team="infra")
        eng.record_variance(variance_id="VAR-002", team="platform")
        results = eng.list_variances(team="infra")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_variance(variance_id=f"VAR-{i}")
        assert len(eng.list_variances(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            variance_id="VAR-001",
            variance_type=VarianceType.SPIKE,
            analysis_score=65.0,
            threshold=80.0,
            breached=True,
            description="Spike detected",
        )
        assert a.variance_id == "VAR-001"
        assert a.variance_type == VarianceType.SPIKE
        assert a.analysis_score == 65.0
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(variance_id=f"VAR-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_variance_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeVarianceDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_variance(
            variance_id="VAR-001",
            variance_type=VarianceType.UNFAVORABLE,
            variance_pct=15.0,
        )
        eng.record_variance(
            variance_id="VAR-002",
            variance_type=VarianceType.UNFAVORABLE,
            variance_pct=25.0,
        )
        result = eng.analyze_variance_distribution()
        assert "unfavorable" in result
        assert result["unfavorable"]["count"] == 2
        assert result["unfavorable"]["avg_variance_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_variance_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_variances
# ---------------------------------------------------------------------------


class TestIdentifyHighVariances:
    def test_detects_high(self):
        eng = _engine()
        eng.record_variance(
            variance_id="VAR-001",
            variance_severity=VarianceSeverity.CRITICAL,
            variance_pct=40.0,
        )
        eng.record_variance(
            variance_id="VAR-002",
            variance_severity=VarianceSeverity.LOW,
            variance_pct=5.0,
        )
        results = eng.identify_high_variances()
        assert len(results) == 1
        assert results[0]["variance_id"] == "VAR-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_variances() == []


# ---------------------------------------------------------------------------
# rank_by_variance
# ---------------------------------------------------------------------------


class TestRankByVariance:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_variance(
            variance_id="VAR-001",
            service="high-var-svc",
            variance_pct=45.0,
        )
        eng.record_variance(
            variance_id="VAR-002",
            service="low-var-svc",
            variance_pct=3.0,
        )
        results = eng.rank_by_variance()
        assert len(results) == 2
        assert results[0]["service"] == "high-var-svc"
        assert results[0]["avg_variance_pct"] == 45.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_variance() == []


# ---------------------------------------------------------------------------
# detect_variance_trends
# ---------------------------------------------------------------------------


class TestDetectVarianceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(variance_id="VAR-001", analysis_score=50.0)
        result = eng.detect_variance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(variance_id="VAR-001", analysis_score=30.0)
        eng.add_analysis(variance_id="VAR-002", analysis_score=30.0)
        eng.add_analysis(variance_id="VAR-003", analysis_score=80.0)
        eng.add_analysis(variance_id="VAR-004", analysis_score=80.0)
        result = eng.detect_variance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_variance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_variance_pct=20.0)
        eng.record_variance(
            variance_id="VAR-001",
            variance_type=VarianceType.UNFAVORABLE,
            variance_severity=VarianceSeverity.CRITICAL,
            variance_source=VarianceSource.COMPUTE,
            variance_pct=35.0,
            service="compute-cluster",
        )
        report = eng.generate_report()
        assert isinstance(report, CostVarianceReport)
        assert report.total_records == 1
        assert report.high_variance_count == 1
        assert len(report.top_variances) == 1
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
        eng.record_variance(variance_id="VAR-001")
        eng.add_analysis(variance_id="VAR-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_variance(
            variance_id="VAR-001",
            variance_type=VarianceType.UNFAVORABLE,
            team="infra",
            service="compute-svc",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "unfavorable" in stats["type_distribution"]

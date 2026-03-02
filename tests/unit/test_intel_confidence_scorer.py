"""Tests for shieldops.security.intel_confidence_scorer — IntelConfidenceScorer."""

from __future__ import annotations

from shieldops.security.intel_confidence_scorer import (
    ConfidenceAnalysis,
    ConfidenceGrade,
    ConfidenceRecord,
    ConfidenceReport,
    IntelConfidenceScorer,
    IntelSource,
    ScoringMethod,
)


def _engine(**kw) -> IntelConfidenceScorer:
    return IntelConfidenceScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_intelsource_val1(self):
        assert IntelSource.HUMINT == "humint"

    def test_intelsource_val2(self):
        assert IntelSource.SIGINT == "sigint"

    def test_intelsource_val3(self):
        assert IntelSource.OSINT == "osint"

    def test_intelsource_val4(self):
        assert IntelSource.TECHINT == "techint"

    def test_intelsource_val5(self):
        assert IntelSource.GEOINT == "geoint"

    def test_confidencegrade_val1(self):
        assert ConfidenceGrade.VERIFIED == "verified"

    def test_confidencegrade_val2(self):
        assert ConfidenceGrade.PROBABLE == "probable"

    def test_confidencegrade_val3(self):
        assert ConfidenceGrade.POSSIBLE == "possible"

    def test_confidencegrade_val4(self):
        assert ConfidenceGrade.DOUBTFUL == "doubtful"

    def test_confidencegrade_val5(self):
        assert ConfidenceGrade.IMPROBABLE == "improbable"

    def test_scoringmethod_val1(self):
        assert ScoringMethod.ANALYTIC == "analytic"

    def test_scoringmethod_val2(self):
        assert ScoringMethod.STATISTICAL == "statistical"

    def test_scoringmethod_val3(self):
        assert ScoringMethod.MACHINE_LEARNING == "machine_learning"

    def test_scoringmethod_val4(self):
        assert ScoringMethod.CONSENSUS == "consensus"

    def test_scoringmethod_val5(self):
        assert ScoringMethod.HEURISTIC == "heuristic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = ConfidenceRecord()
        assert r.id
        assert r.intel_name == ""
        assert r.intel_source == IntelSource.OSINT
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ConfidenceAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ConfidenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_source == {}
        assert r.by_grade == {}
        assert r.by_method == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_confidence(
            intel_name="test",
            intel_source=IntelSource.SIGINT,
            confidence_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.intel_name == "test"
        assert r.intel_source == IntelSource.SIGINT
        assert r.confidence_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_confidence(intel_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_confidence(intel_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_confidence(intel_name="a")
        eng.record_confidence(intel_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_confidence(intel_name="a", intel_source=IntelSource.HUMINT)
        eng.record_confidence(intel_name="b", intel_source=IntelSource.SIGINT)
        results = eng.list_records(intel_source=IntelSource.HUMINT)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_confidence(intel_name="a", confidence_grade=ConfidenceGrade.VERIFIED)
        eng.record_confidence(intel_name="b", confidence_grade=ConfidenceGrade.PROBABLE)
        results = eng.list_records(confidence_grade=ConfidenceGrade.VERIFIED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_confidence(intel_name="a", team="sec")
        eng.record_confidence(intel_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_confidence(intel_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            intel_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(intel_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_confidence(
            intel_name="a",
            intel_source=IntelSource.HUMINT,
            confidence_score=90.0,
        )
        eng.record_confidence(
            intel_name="b",
            intel_source=IntelSource.HUMINT,
            confidence_score=70.0,
        )
        result = eng.analyze_source_distribution()
        assert "humint" in result
        assert result["humint"]["count"] == 2
        assert result["humint"]["avg_confidence_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_source_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_confidence(intel_name="a", confidence_score=60.0)
        eng.record_confidence(intel_name="b", confidence_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["intel_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_confidence(intel_name="a", confidence_score=50.0)
        eng.record_confidence(intel_name="b", confidence_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["confidence_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_confidence(intel_name="a", service="auth-svc", confidence_score=90.0)
        eng.record_confidence(intel_name="b", service="api-gw", confidence_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_confidence_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(intel_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(intel_name="t1", analysis_score=20.0)
        eng.add_analysis(intel_name="t2", analysis_score=20.0)
        eng.add_analysis(intel_name="t3", analysis_score=80.0)
        eng.add_analysis(intel_name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_confidence(
            intel_name="test",
            intel_source=IntelSource.SIGINT,
            confidence_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ConfidenceReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
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
        eng.record_confidence(intel_name="test")
        eng.add_analysis(intel_name="test")
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
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_confidence(
            intel_name="test",
            intel_source=IntelSource.HUMINT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "humint" in stats["source_distribution"]

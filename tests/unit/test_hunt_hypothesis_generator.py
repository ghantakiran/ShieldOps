"""Tests for shieldops.security.hunt_hypothesis_generator — HuntHypothesisGenerator."""

from __future__ import annotations

from shieldops.security.hunt_hypothesis_generator import (
    ConfidenceLevel,
    HuntHypothesisGenerator,
    HypothesisAnalysis,
    HypothesisRecord,
    HypothesisReport,
    HypothesisSource,
    HypothesisStatus,
)


def _engine(**kw) -> HuntHypothesisGenerator:
    return HuntHypothesisGenerator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_threat_intel(self):
        assert HypothesisSource.THREAT_INTEL == "threat_intel"

    def test_source_detection_gap(self):
        assert HypothesisSource.DETECTION_GAP == "detection_gap"

    def test_source_anomaly(self):
        assert HypothesisSource.ANOMALY == "anomaly"

    def test_source_incident_pattern(self):
        assert HypothesisSource.INCIDENT_PATTERN == "incident_pattern"

    def test_source_external_report(self):
        assert HypothesisSource.EXTERNAL_REPORT == "external_report"

    def test_status_active(self):
        assert HypothesisStatus.ACTIVE == "active"

    def test_status_validated(self):
        assert HypothesisStatus.VALIDATED == "validated"

    def test_status_disproven(self):
        assert HypothesisStatus.DISPROVEN == "disproven"

    def test_status_pending(self):
        assert HypothesisStatus.PENDING == "pending"

    def test_status_archived(self):
        assert HypothesisStatus.ARCHIVED == "archived"

    def test_confidence_very_high(self):
        assert ConfidenceLevel.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert ConfidenceLevel.HIGH == "high"

    def test_confidence_medium(self):
        assert ConfidenceLevel.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ConfidenceLevel.LOW == "low"

    def test_confidence_speculative(self):
        assert ConfidenceLevel.SPECULATIVE == "speculative"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_hypothesis_record_defaults(self):
        r = HypothesisRecord()
        assert r.id
        assert r.hypothesis_name == ""
        assert r.hypothesis_source == HypothesisSource.THREAT_INTEL
        assert r.hypothesis_status == HypothesisStatus.ACTIVE
        assert r.confidence_level == ConfidenceLevel.VERY_HIGH
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_hypothesis_analysis_defaults(self):
        c = HypothesisAnalysis()
        assert c.id
        assert c.hypothesis_name == ""
        assert c.hypothesis_source == HypothesisSource.THREAT_INTEL
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_hypothesis_report_defaults(self):
        r = HypothesisReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_quality_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_source == {}
        assert r.by_status == {}
        assert r.by_confidence == {}
        assert r.top_low_quality == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_hypothesis
# ---------------------------------------------------------------------------


class TestRecordHypothesis:
    def test_basic(self):
        eng = _engine()
        r = eng.record_hypothesis(
            hypothesis_name="hyp-001",
            hypothesis_source=HypothesisSource.DETECTION_GAP,
            hypothesis_status=HypothesisStatus.VALIDATED,
            confidence_level=ConfidenceLevel.HIGH,
            quality_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.hypothesis_name == "hyp-001"
        assert r.hypothesis_source == HypothesisSource.DETECTION_GAP
        assert r.hypothesis_status == HypothesisStatus.VALIDATED
        assert r.confidence_level == ConfidenceLevel.HIGH
        assert r.quality_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_hypothesis(hypothesis_name=f"hyp-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_hypothesis
# ---------------------------------------------------------------------------


class TestGetHypothesis:
    def test_found(self):
        eng = _engine()
        r = eng.record_hypothesis(
            hypothesis_name="hyp-001",
            confidence_level=ConfidenceLevel.VERY_HIGH,
        )
        result = eng.get_hypothesis(r.id)
        assert result is not None
        assert result.confidence_level == ConfidenceLevel.VERY_HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_hypothesis("nonexistent") is None


# ---------------------------------------------------------------------------
# list_hypotheses
# ---------------------------------------------------------------------------


class TestListHypotheses:
    def test_list_all(self):
        eng = _engine()
        eng.record_hypothesis(hypothesis_name="hyp-001")
        eng.record_hypothesis(hypothesis_name="hyp-002")
        assert len(eng.list_hypotheses()) == 2

    def test_filter_by_hypothesis_source(self):
        eng = _engine()
        eng.record_hypothesis(
            hypothesis_name="hyp-001",
            hypothesis_source=HypothesisSource.THREAT_INTEL,
        )
        eng.record_hypothesis(
            hypothesis_name="hyp-002",
            hypothesis_source=HypothesisSource.ANOMALY,
        )
        results = eng.list_hypotheses(hypothesis_source=HypothesisSource.THREAT_INTEL)
        assert len(results) == 1

    def test_filter_by_hypothesis_status(self):
        eng = _engine()
        eng.record_hypothesis(
            hypothesis_name="hyp-001",
            hypothesis_status=HypothesisStatus.ACTIVE,
        )
        eng.record_hypothesis(
            hypothesis_name="hyp-002",
            hypothesis_status=HypothesisStatus.VALIDATED,
        )
        results = eng.list_hypotheses(hypothesis_status=HypothesisStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_hypothesis(hypothesis_name="hyp-001", team="security")
        eng.record_hypothesis(hypothesis_name="hyp-002", team="platform")
        results = eng.list_hypotheses(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_hypothesis(hypothesis_name=f"hyp-{i}")
        assert len(eng.list_hypotheses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            hypothesis_name="hyp-001",
            hypothesis_source=HypothesisSource.DETECTION_GAP,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low quality detected",
        )
        assert a.hypothesis_name == "hyp-001"
        assert a.hypothesis_source == HypothesisSource.DETECTION_GAP
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(hypothesis_name=f"hyp-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_hypothesis_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_hypothesis(
            hypothesis_name="hyp-001",
            hypothesis_source=HypothesisSource.THREAT_INTEL,
            quality_score=90.0,
        )
        eng.record_hypothesis(
            hypothesis_name="hyp-002",
            hypothesis_source=HypothesisSource.THREAT_INTEL,
            quality_score=70.0,
        )
        result = eng.analyze_hypothesis_distribution()
        assert "threat_intel" in result
        assert result["threat_intel"]["count"] == 2
        assert result["threat_intel"]["avg_quality_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_hypothesis_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_quality_hypotheses
# ---------------------------------------------------------------------------


class TestIdentifyLowQualityHypotheses:
    def test_detects_below_threshold(self):
        eng = _engine(hypothesis_quality_threshold=80.0)
        eng.record_hypothesis(hypothesis_name="hyp-001", quality_score=60.0)
        eng.record_hypothesis(hypothesis_name="hyp-002", quality_score=90.0)
        results = eng.identify_low_quality_hypotheses()
        assert len(results) == 1
        assert results[0]["hypothesis_name"] == "hyp-001"

    def test_sorted_ascending(self):
        eng = _engine(hypothesis_quality_threshold=80.0)
        eng.record_hypothesis(hypothesis_name="hyp-001", quality_score=50.0)
        eng.record_hypothesis(hypothesis_name="hyp-002", quality_score=30.0)
        results = eng.identify_low_quality_hypotheses()
        assert len(results) == 2
        assert results[0]["quality_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_quality_hypotheses() == []


# ---------------------------------------------------------------------------
# rank_by_quality
# ---------------------------------------------------------------------------


class TestRankByQuality:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_hypothesis(hypothesis_name="hyp-001", service="auth-svc", quality_score=90.0)
        eng.record_hypothesis(hypothesis_name="hyp-002", service="api-gw", quality_score=50.0)
        results = eng.rank_by_quality()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_quality_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality() == []


# ---------------------------------------------------------------------------
# detect_hypothesis_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(hypothesis_name="hyp-001", analysis_score=50.0)
        result = eng.detect_hypothesis_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(hypothesis_name="hyp-001", analysis_score=20.0)
        eng.add_analysis(hypothesis_name="hyp-002", analysis_score=20.0)
        eng.add_analysis(hypothesis_name="hyp-003", analysis_score=80.0)
        eng.add_analysis(hypothesis_name="hyp-004", analysis_score=80.0)
        result = eng.detect_hypothesis_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_hypothesis_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(hypothesis_quality_threshold=80.0)
        eng.record_hypothesis(
            hypothesis_name="hyp-001",
            hypothesis_source=HypothesisSource.DETECTION_GAP,
            hypothesis_status=HypothesisStatus.VALIDATED,
            confidence_level=ConfidenceLevel.HIGH,
            quality_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, HypothesisReport)
        assert report.total_records == 1
        assert report.low_quality_count == 1
        assert len(report.top_low_quality) == 1
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
        eng.record_hypothesis(hypothesis_name="hyp-001")
        eng.add_analysis(hypothesis_name="hyp-001")
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
        eng.record_hypothesis(
            hypothesis_name="hyp-001",
            hypothesis_source=HypothesisSource.THREAT_INTEL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "threat_intel" in stats["source_distribution"]

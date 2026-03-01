"""Tests for shieldops.observability.alert_noise_profiler — AlertNoiseProfiler."""

from __future__ import annotations

from shieldops.observability.alert_noise_profiler import (
    AlertNoiseProfiler,
    AlertNoiseReport,
    NoiseAssessment,
    NoiseCategory,
    NoiseImpact,
    NoiseProfileRecord,
    NoiseSource,
)


def _engine(**kw) -> AlertNoiseProfiler:
    return AlertNoiseProfiler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_false_positive(self):
        assert NoiseCategory.FALSE_POSITIVE == "false_positive"

    def test_category_duplicate(self):
        assert NoiseCategory.DUPLICATE == "duplicate"

    def test_category_transient(self):
        assert NoiseCategory.TRANSIENT == "transient"

    def test_category_stale(self):
        assert NoiseCategory.STALE == "stale"

    def test_category_actionable(self):
        assert NoiseCategory.ACTIONABLE == "actionable"

    def test_source_threshold_misconfigured(self):
        assert NoiseSource.THRESHOLD_MISCONFIGURED == "threshold_misconfigured"

    def test_source_flapping_metric(self):
        assert NoiseSource.FLAPPING_METRIC == "flapping_metric"

    def test_source_dependency_cascade(self):
        assert NoiseSource.DEPENDENCY_CASCADE == "dependency_cascade"

    def test_source_monitoring_gap(self):
        assert NoiseSource.MONITORING_GAP == "monitoring_gap"

    def test_source_legitimate(self):
        assert NoiseSource.LEGITIMATE == "legitimate"

    def test_impact_critical(self):
        assert NoiseImpact.CRITICAL == "critical"

    def test_impact_high(self):
        assert NoiseImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert NoiseImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert NoiseImpact.LOW == "low"

    def test_impact_negligible(self):
        assert NoiseImpact.NEGLIGIBLE == "negligible"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_noise_profile_record_defaults(self):
        r = NoiseProfileRecord()
        assert r.id
        assert r.profile_id == ""
        assert r.noise_category == NoiseCategory.ACTIONABLE
        assert r.noise_source == NoiseSource.LEGITIMATE
        assert r.noise_impact == NoiseImpact.NEGLIGIBLE
        assert r.noise_ratio == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_noise_assessment_defaults(self):
        a = NoiseAssessment()
        assert a.id
        assert a.profile_id == ""
        assert a.noise_category == NoiseCategory.ACTIONABLE
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_alert_noise_report_defaults(self):
        r = AlertNoiseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_noise_count == 0
        assert r.avg_noise_ratio == 0.0
        assert r.by_category == {}
        assert r.by_source == {}
        assert r.by_impact == {}
        assert r.top_noisy_rules == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_profile
# ---------------------------------------------------------------------------


class TestRecordProfile:
    def test_basic(self):
        eng = _engine()
        r = eng.record_profile(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
            noise_source=NoiseSource.THRESHOLD_MISCONFIGURED,
            noise_impact=NoiseImpact.HIGH,
            noise_ratio=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.profile_id == "PROF-001"
        assert r.noise_category == NoiseCategory.FALSE_POSITIVE
        assert r.noise_source == NoiseSource.THRESHOLD_MISCONFIGURED
        assert r.noise_impact == NoiseImpact.HIGH
        assert r.noise_ratio == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_profile(profile_id=f"PROF-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_found(self):
        eng = _engine()
        r = eng.record_profile(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
        )
        result = eng.get_profile(r.id)
        assert result is not None
        assert result.noise_category == NoiseCategory.FALSE_POSITIVE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_profile("nonexistent") is None


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_list_all(self):
        eng = _engine()
        eng.record_profile(profile_id="PROF-001")
        eng.record_profile(profile_id="PROF-002")
        assert len(eng.list_profiles()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_profile(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
        )
        eng.record_profile(
            profile_id="PROF-002",
            noise_category=NoiseCategory.DUPLICATE,
        )
        results = eng.list_profiles(
            noise_category=NoiseCategory.FALSE_POSITIVE,
        )
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_profile(
            profile_id="PROF-001",
            noise_source=NoiseSource.THRESHOLD_MISCONFIGURED,
        )
        eng.record_profile(
            profile_id="PROF-002",
            noise_source=NoiseSource.LEGITIMATE,
        )
        results = eng.list_profiles(
            noise_source=NoiseSource.THRESHOLD_MISCONFIGURED,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_profile(profile_id="PROF-001", service="api-gateway")
        eng.record_profile(profile_id="PROF-002", service="auth")
        results = eng.list_profiles(service="api-gateway")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_profile(profile_id=f"PROF-{i}")
        assert len(eng.list_profiles(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
            assessment_score=72.0,
            threshold=60.0,
            breached=True,
            description="High false positive rate",
        )
        assert a.profile_id == "PROF-001"
        assert a.noise_category == NoiseCategory.FALSE_POSITIVE
        assert a.assessment_score == 72.0
        assert a.threshold == 60.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(profile_id=f"PROF-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_noise_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeNoiseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_profile(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
            noise_ratio=40.0,
        )
        eng.record_profile(
            profile_id="PROF-002",
            noise_category=NoiseCategory.FALSE_POSITIVE,
            noise_ratio=60.0,
        )
        result = eng.analyze_noise_distribution()
        assert "false_positive" in result
        assert result["false_positive"]["count"] == 2
        assert result["false_positive"]["avg_noise_ratio"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_noise_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_noise
# ---------------------------------------------------------------------------


class TestIdentifyHighNoise:
    def test_detects_high_noise(self):
        eng = _engine(max_noise_ratio=30.0)
        eng.record_profile(
            profile_id="PROF-001",
            noise_ratio=50.0,
        )
        eng.record_profile(
            profile_id="PROF-002",
            noise_ratio=10.0,
        )
        results = eng.identify_high_noise()
        assert len(results) == 1
        assert results[0]["profile_id"] == "PROF-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_noise() == []


# ---------------------------------------------------------------------------
# rank_by_noise_ratio
# ---------------------------------------------------------------------------


class TestRankByNoiseRatio:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_profile(
            profile_id="PROF-001",
            service="api-gateway",
            noise_ratio=80.0,
        )
        eng.record_profile(
            profile_id="PROF-002",
            service="auth",
            noise_ratio=20.0,
        )
        results = eng.rank_by_noise_ratio()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_noise_ratio"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_noise_ratio() == []


# ---------------------------------------------------------------------------
# detect_noise_trends
# ---------------------------------------------------------------------------


class TestDetectNoiseTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(profile_id="PROF-001", assessment_score=50.0)
        result = eng.detect_noise_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        eng.add_assessment(profile_id="PROF-001", assessment_score=10.0)
        eng.add_assessment(profile_id="PROF-002", assessment_score=10.0)
        eng.add_assessment(profile_id="PROF-003", assessment_score=80.0)
        eng.add_assessment(profile_id="PROF-004", assessment_score=80.0)
        result = eng.detect_noise_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_noise_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_noise_ratio=30.0)
        eng.record_profile(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
            noise_source=NoiseSource.THRESHOLD_MISCONFIGURED,
            noise_ratio=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AlertNoiseReport)
        assert report.total_records == 1
        assert report.high_noise_count == 1
        assert len(report.top_noisy_rules) == 1
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
        eng.record_profile(profile_id="PROF-001")
        eng.add_assessment(profile_id="PROF-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["noise_category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_profile(
            profile_id="PROF-001",
            noise_category=NoiseCategory.FALSE_POSITIVE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "false_positive" in stats["noise_category_distribution"]

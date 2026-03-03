"""Tests for shieldops.security.dependency_freshness_enforcer."""

from __future__ import annotations

from shieldops.security.dependency_freshness_enforcer import (
    DependencyFreshnessEnforcer,
    DependencyFreshnessReport,
    FreshnessAnalysis,
    FreshnessLevel,
    FreshnessRecord,
    PackageEcosystem,
    UpdateUrgency,
)


def _engine(**kw) -> DependencyFreshnessEnforcer:
    return DependencyFreshnessEnforcer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_freshness_current(self):
        assert FreshnessLevel.CURRENT == "current"

    def test_freshness_outdated(self):
        assert FreshnessLevel.OUTDATED == "outdated"

    def test_freshness_stale(self):
        assert FreshnessLevel.STALE == "stale"

    def test_freshness_abandoned(self):
        assert FreshnessLevel.ABANDONED == "abandoned"

    def test_freshness_unknown(self):
        assert FreshnessLevel.UNKNOWN == "unknown"

    def test_urgency_critical(self):
        assert UpdateUrgency.CRITICAL == "critical"

    def test_urgency_high(self):
        assert UpdateUrgency.HIGH == "high"

    def test_urgency_medium(self):
        assert UpdateUrgency.MEDIUM == "medium"

    def test_urgency_low(self):
        assert UpdateUrgency.LOW == "low"

    def test_urgency_none(self):
        assert UpdateUrgency.NONE == "none"

    def test_ecosystem_npm(self):
        assert PackageEcosystem.NPM == "npm"

    def test_ecosystem_pypi(self):
        assert PackageEcosystem.PYPI == "pypi"

    def test_ecosystem_maven(self):
        assert PackageEcosystem.MAVEN == "maven"

    def test_ecosystem_nuget(self):
        assert PackageEcosystem.NUGET == "nuget"

    def test_ecosystem_cargo(self):
        assert PackageEcosystem.CARGO == "cargo"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_freshness_record_defaults(self):
        r = FreshnessRecord()
        assert r.id
        assert r.package_name == ""
        assert r.freshness_level == FreshnessLevel.CURRENT
        assert r.update_urgency == UpdateUrgency.NONE
        assert r.package_ecosystem == PackageEcosystem.PYPI
        assert r.freshness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_freshness_analysis_defaults(self):
        c = FreshnessAnalysis()
        assert c.id
        assert c.package_name == ""
        assert c.freshness_level == FreshnessLevel.CURRENT
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_dependency_freshness_report_defaults(self):
        r = DependencyFreshnessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_freshness_score == 0.0
        assert r.by_freshness == {}
        assert r.by_urgency == {}
        assert r.by_ecosystem == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_freshness / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_freshness(
            package_name="flask",
            freshness_level=FreshnessLevel.STALE,
            update_urgency=UpdateUrgency.HIGH,
            package_ecosystem=PackageEcosystem.PYPI,
            freshness_score=30.0,
            service="backend",
            team="platform",
        )
        assert r.package_name == "flask"
        assert r.freshness_level == FreshnessLevel.STALE
        assert r.update_urgency == UpdateUrgency.HIGH
        assert r.package_ecosystem == PackageEcosystem.PYPI
        assert r.freshness_score == 30.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_freshness(package_name="django", freshness_score=90.0)
        result = eng.get_freshness(r.id)
        assert result is not None
        assert result.freshness_score == 90.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_freshness("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_freshness(package_name=f"pkg-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_freshness_records
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_freshness(package_name="a")
        eng.record_freshness(package_name="b")
        assert len(eng.list_freshness_records()) == 2

    def test_filter_by_freshness_level(self):
        eng = _engine()
        eng.record_freshness(package_name="a", freshness_level=FreshnessLevel.CURRENT)
        eng.record_freshness(package_name="b", freshness_level=FreshnessLevel.STALE)
        results = eng.list_freshness_records(freshness_level=FreshnessLevel.CURRENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_freshness(package_name="a", team="platform")
        eng.record_freshness(package_name="b", team="security")
        results = eng.list_freshness_records(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_freshness(package_name=f"pkg-{i}")
        assert len(eng.list_freshness_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            package_name="flask",
            freshness_level=FreshnessLevel.STALE,
            analysis_score=30.0,
            threshold=60.0,
            breached=True,
            description="package is stale",
        )
        assert a.package_name == "flask"
        assert a.freshness_level == FreshnessLevel.STALE
        assert a.analysis_score == 30.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(package_name=f"pkg-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_ecosystem(self):
        eng = _engine()
        eng.record_freshness(package_name="a", package_ecosystem=PackageEcosystem.PYPI)
        eng.record_freshness(package_name="b", package_ecosystem=PackageEcosystem.NPM)
        results = eng.list_freshness_records(package_ecosystem=PackageEcosystem.PYPI)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_freshness_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_freshness(
            package_name="a", freshness_level=FreshnessLevel.CURRENT, freshness_score=90.0
        )
        eng.record_freshness(
            package_name="b", freshness_level=FreshnessLevel.CURRENT, freshness_score=70.0
        )
        result = eng.analyze_freshness_distribution()
        assert "current" in result
        assert result["current"]["count"] == 2
        assert result["current"]["avg_freshness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_freshness_distribution() == {}


# ---------------------------------------------------------------------------
# identify_freshness_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(freshness_gap_threshold=60.0)
        eng.record_freshness(package_name="a", freshness_score=40.0)
        eng.record_freshness(package_name="b", freshness_score=80.0)
        results = eng.identify_freshness_gaps()
        assert len(results) == 1
        assert results[0]["package_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(freshness_gap_threshold=80.0)
        eng.record_freshness(package_name="a", freshness_score=50.0)
        eng.record_freshness(package_name="b", freshness_score=20.0)
        results = eng.identify_freshness_gaps()
        assert len(results) == 2
        assert results[0]["freshness_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_freshness
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_freshness(package_name="a", service="backend", freshness_score=90.0)
        eng.record_freshness(package_name="b", service="frontend", freshness_score=30.0)
        results = eng.rank_by_freshness()
        assert len(results) == 2
        assert results[0]["service"] == "frontend"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_freshness() == []


# ---------------------------------------------------------------------------
# detect_freshness_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(package_name="pkg", analysis_score=50.0)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        result = eng.detect_freshness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_freshness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(freshness_gap_threshold=60.0)
        eng.record_freshness(
            package_name="flask",
            freshness_level=FreshnessLevel.STALE,
            update_urgency=UpdateUrgency.HIGH,
            freshness_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DependencyFreshnessReport)
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


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_freshness(package_name="pkg")
        eng.add_analysis(package_name="pkg")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_freshness(
            package_name="flask",
            freshness_level=FreshnessLevel.CURRENT,
            service="backend",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "current" in stats["freshness_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_freshness(package_name=f"pkg-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].package_name == "pkg-4"

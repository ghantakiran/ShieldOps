"""Tests for shieldops.analytics.dependency_freshness — DependencyFreshnessMonitor.

Covers UpdateUrgency, DependencyEcosystem, and FreshnessGrade enums,
DependencyRecord / FreshnessScore / FreshnessReport models, and all
DependencyFreshnessMonitor operations including dependency registration,
freshness scoring, EOL detection, security update identification, service
ranking, ecosystem health analysis, and report generation.
"""

from __future__ import annotations

from shieldops.analytics.dependency_freshness import (
    DependencyEcosystem,
    DependencyFreshnessMonitor,
    DependencyRecord,
    FreshnessGrade,
    FreshnessReport,
    FreshnessScore,
    UpdateUrgency,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> DependencyFreshnessMonitor:
    return DependencyFreshnessMonitor(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of UpdateUrgency, DependencyEcosystem, and FreshnessGrade."""

    # -- UpdateUrgency (5 members) --------------------------------------------

    def test_urgency_current(self):
        assert UpdateUrgency.CURRENT == "current"

    def test_urgency_minor_behind(self):
        assert UpdateUrgency.MINOR_BEHIND == "minor_behind"

    def test_urgency_major_behind(self):
        assert UpdateUrgency.MAJOR_BEHIND == "major_behind"

    def test_urgency_end_of_life(self):
        assert UpdateUrgency.END_OF_LIFE == "end_of_life"

    def test_urgency_security_update(self):
        assert UpdateUrgency.SECURITY_UPDATE == "security_update"

    # -- DependencyEcosystem (6 members) --------------------------------------

    def test_ecosystem_pip(self):
        assert DependencyEcosystem.PIP == "pip"

    def test_ecosystem_npm(self):
        assert DependencyEcosystem.NPM == "npm"

    def test_ecosystem_maven(self):
        assert DependencyEcosystem.MAVEN == "maven"

    def test_ecosystem_cargo(self):
        assert DependencyEcosystem.CARGO == "cargo"

    def test_ecosystem_go_mod(self):
        assert DependencyEcosystem.GO_MOD == "go_mod"

    def test_ecosystem_nuget(self):
        assert DependencyEcosystem.NUGET == "nuget"

    # -- FreshnessGrade (5 members) -------------------------------------------

    def test_grade_a(self):
        assert FreshnessGrade.A == "A"

    def test_grade_b(self):
        assert FreshnessGrade.B == "B"

    def test_grade_c(self):
        assert FreshnessGrade.C == "C"

    def test_grade_d(self):
        assert FreshnessGrade.D == "D"

    def test_grade_f(self):
        assert FreshnessGrade.F == "F"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_dependency_record_defaults(self):
        d = DependencyRecord()
        assert d.id
        assert d.package_name == ""
        assert d.current_version == ""
        assert d.latest_version == ""
        assert d.ecosystem == DependencyEcosystem.PIP
        assert d.service_name == ""
        assert d.urgency == UpdateUrgency.CURRENT
        assert d.is_direct is True
        assert d.has_security_advisory is False
        assert d.created_at > 0

    def test_freshness_score_defaults(self):
        s = FreshnessScore()
        assert s.id
        assert s.service_name == ""
        assert s.total_dependencies == 0
        assert s.up_to_date_count == 0
        assert s.behind_count == 0
        assert s.eol_count == 0
        assert s.security_update_count == 0
        assert s.freshness_pct == 0.0
        assert s.grade == FreshnessGrade.C
        assert s.calculated_at > 0

    def test_freshness_report_defaults(self):
        r = FreshnessReport()
        assert r.total_dependencies == 0
        assert r.total_services == 0
        assert r.avg_freshness_pct == 0.0
        assert r.eol_count == 0
        assert r.security_update_count == 0
        assert r.ecosystem_distribution == {}
        assert r.grade_distribution == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RegisterDependency
# ===========================================================================


class TestRegisterDependency:
    """Test DependencyFreshnessMonitor.register_dependency."""

    def test_basic_registration(self):
        eng = _engine()
        d = eng.register_dependency(
            package_name="requests",
            current_version="2.28.0",
            latest_version="2.31.0",
            ecosystem=DependencyEcosystem.PIP,
            service_name="auth-svc",
            urgency=UpdateUrgency.MINOR_BEHIND,
        )
        assert d.id
        assert d.package_name == "requests"
        assert d.current_version == "2.28.0"
        assert d.latest_version == "2.31.0"
        assert d.ecosystem == DependencyEcosystem.PIP
        assert d.service_name == "auth-svc"
        assert d.urgency == UpdateUrgency.MINOR_BEHIND
        assert d.is_direct is True

    def test_eviction_on_overflow(self):
        eng = _engine(max_dependencies=2)
        eng.register_dependency(
            package_name="pkg-a",
            current_version="1.0",
            latest_version="1.0",
            service_name="svc",
        )
        eng.register_dependency(
            package_name="pkg-b",
            current_version="1.0",
            latest_version="1.0",
            service_name="svc",
        )
        d3 = eng.register_dependency(
            package_name="pkg-c",
            current_version="1.0",
            latest_version="2.0",
            service_name="svc",
        )
        deps = eng.list_dependencies(limit=10)
        assert len(deps) == 2
        assert deps[-1].id == d3.id


# ===========================================================================
# GetDependency
# ===========================================================================


class TestGetDependency:
    """Test DependencyFreshnessMonitor.get_dependency."""

    def test_found(self):
        eng = _engine()
        d = eng.register_dependency(
            package_name="fastapi",
            current_version="0.100.0",
            latest_version="0.104.0",
            service_name="api-svc",
        )
        assert eng.get_dependency(d.id) is d

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent-id") is None


# ===========================================================================
# ListDependencies
# ===========================================================================


class TestListDependencies:
    """Test DependencyFreshnessMonitor.list_dependencies with various filters."""

    def test_all_dependencies(self):
        eng = _engine()
        eng.register_dependency(
            package_name="pkg-a",
            current_version="1.0",
            latest_version="1.0",
            service_name="svc-a",
        )
        eng.register_dependency(
            package_name="pkg-b",
            current_version="1.0",
            latest_version="2.0",
            service_name="svc-b",
        )
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_ecosystem(self):
        eng = _engine()
        eng.register_dependency(
            package_name="requests",
            current_version="2.28.0",
            latest_version="2.31.0",
            ecosystem=DependencyEcosystem.PIP,
            service_name="svc-a",
        )
        eng.register_dependency(
            package_name="express",
            current_version="4.17.0",
            latest_version="4.18.0",
            ecosystem=DependencyEcosystem.NPM,
            service_name="svc-b",
        )
        results = eng.list_dependencies(ecosystem=DependencyEcosystem.NPM)
        assert len(results) == 1
        assert results[0].ecosystem == DependencyEcosystem.NPM

    def test_filter_by_urgency(self):
        eng = _engine()
        eng.register_dependency(
            package_name="pkg-current",
            current_version="1.0",
            latest_version="1.0",
            urgency=UpdateUrgency.CURRENT,
            service_name="svc",
        )
        eng.register_dependency(
            package_name="pkg-eol",
            current_version="0.9",
            latest_version="2.0",
            urgency=UpdateUrgency.END_OF_LIFE,
            service_name="svc",
        )
        results = eng.list_dependencies(urgency=UpdateUrgency.END_OF_LIFE)
        assert len(results) == 1
        assert results[0].urgency == UpdateUrgency.END_OF_LIFE

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_dependency(
            package_name="pkg-a",
            current_version="1.0",
            latest_version="1.0",
            service_name="auth-svc",
        )
        eng.register_dependency(
            package_name="pkg-b",
            current_version="1.0",
            latest_version="1.0",
            service_name="billing-svc",
        )
        eng.register_dependency(
            package_name="pkg-c",
            current_version="1.0",
            latest_version="1.0",
            service_name="auth-svc",
        )
        results = eng.list_dependencies(service_name="auth-svc")
        assert len(results) == 2
        assert all(d.service_name == "auth-svc" for d in results)


# ===========================================================================
# CalculateFreshnessScore
# ===========================================================================


class TestCalculateFreshnessScore:
    """Test DependencyFreshnessMonitor.calculate_freshness_score."""

    def test_all_current_grade_a(self):
        eng = _engine()
        for i in range(10):
            eng.register_dependency(
                package_name=f"pkg-{i}",
                current_version="1.0.0",
                latest_version="1.0.0",
                urgency=UpdateUrgency.CURRENT,
                service_name="fresh-svc",
            )
        score = eng.calculate_freshness_score("fresh-svc")
        assert score.service_name == "fresh-svc"
        assert score.total_dependencies == 10
        assert score.up_to_date_count == 10
        assert score.freshness_pct == 100.0
        assert score.grade == FreshnessGrade.A

    def test_mixed_deps_low_grade(self):
        eng = _engine()
        # 2 current, 3 behind, 3 EOL, 2 security = 10 total
        # freshness = 2/10 = 20% -> grade F
        for i in range(2):
            eng.register_dependency(
                package_name=f"current-{i}",
                current_version="1.0",
                latest_version="1.0",
                urgency=UpdateUrgency.CURRENT,
                service_name="stale-svc",
            )
        for i in range(3):
            eng.register_dependency(
                package_name=f"behind-{i}",
                current_version="1.0",
                latest_version="3.0",
                urgency=UpdateUrgency.MAJOR_BEHIND,
                service_name="stale-svc",
            )
        for i in range(3):
            eng.register_dependency(
                package_name=f"eol-{i}",
                current_version="0.1",
                latest_version="2.0",
                urgency=UpdateUrgency.END_OF_LIFE,
                service_name="stale-svc",
            )
        for i in range(2):
            eng.register_dependency(
                package_name=f"sec-{i}",
                current_version="1.0",
                latest_version="1.1",
                urgency=UpdateUrgency.SECURITY_UPDATE,
                service_name="stale-svc",
            )
        score = eng.calculate_freshness_score("stale-svc")
        assert score.total_dependencies == 10
        assert score.up_to_date_count == 2
        assert score.freshness_pct == 20.0
        assert score.grade == FreshnessGrade.F


# ===========================================================================
# DetectEolDependencies
# ===========================================================================


class TestDetectEolDependencies:
    """Test DependencyFreshnessMonitor.detect_eol_dependencies."""

    def test_with_eol_deps(self):
        eng = _engine()
        eng.register_dependency(
            package_name="old-lib",
            current_version="0.9",
            latest_version="3.0",
            urgency=UpdateUrgency.END_OF_LIFE,
            service_name="svc-a",
        )
        eng.register_dependency(
            package_name="fresh-lib",
            current_version="1.0",
            latest_version="1.0",
            urgency=UpdateUrgency.CURRENT,
            service_name="svc-a",
        )
        eol = eng.detect_eol_dependencies()
        assert len(eol) == 1
        assert eol[0].package_name == "old-lib"
        assert eol[0].urgency == UpdateUrgency.END_OF_LIFE


# ===========================================================================
# IdentifySecurityUpdates
# ===========================================================================


class TestIdentifySecurityUpdates:
    """Test DependencyFreshnessMonitor.identify_security_updates."""

    def test_with_security_advisory(self):
        eng = _engine()
        eng.register_dependency(
            package_name="vuln-lib",
            current_version="1.0",
            latest_version="1.1",
            urgency=UpdateUrgency.SECURITY_UPDATE,
            has_security_advisory=True,
            service_name="svc-a",
        )
        eng.register_dependency(
            package_name="safe-lib",
            current_version="2.0",
            latest_version="2.0",
            urgency=UpdateUrgency.CURRENT,
            service_name="svc-a",
        )
        # Also catch deps that only have the advisory flag, not the urgency
        eng.register_dependency(
            package_name="advisory-lib",
            current_version="1.5",
            latest_version="1.6",
            urgency=UpdateUrgency.MINOR_BEHIND,
            has_security_advisory=True,
            service_name="svc-b",
        )
        security = eng.identify_security_updates()
        assert len(security) == 2
        names = {d.package_name for d in security}
        assert "vuln-lib" in names
        assert "advisory-lib" in names


# ===========================================================================
# RankServicesByFreshness
# ===========================================================================


class TestRankServicesByFreshness:
    """Test DependencyFreshnessMonitor.rank_services_by_freshness."""

    def test_multiple_services_ranked(self):
        eng = _engine()
        # fresh-svc: all current -> 100%
        for i in range(5):
            eng.register_dependency(
                package_name=f"fresh-{i}",
                current_version="1.0",
                latest_version="1.0",
                urgency=UpdateUrgency.CURRENT,
                service_name="fresh-svc",
            )
        # stale-svc: none current -> 0%
        for i in range(5):
            eng.register_dependency(
                package_name=f"stale-{i}",
                current_version="0.1",
                latest_version="3.0",
                urgency=UpdateUrgency.MAJOR_BEHIND,
                service_name="stale-svc",
            )
        ranked = eng.rank_services_by_freshness()
        assert len(ranked) == 2
        assert ranked[0].service_name == "fresh-svc"
        assert ranked[0].freshness_pct == 100.0
        assert ranked[1].service_name == "stale-svc"
        assert ranked[1].freshness_pct == 0.0


# ===========================================================================
# AnalyzeEcosystemHealth
# ===========================================================================


class TestAnalyzeEcosystemHealth:
    """Test DependencyFreshnessMonitor.analyze_ecosystem_health."""

    def test_multiple_ecosystems(self):
        eng = _engine()
        # PIP: 2 current out of 3
        eng.register_dependency(
            package_name="pip-a",
            current_version="1.0",
            latest_version="1.0",
            ecosystem=DependencyEcosystem.PIP,
            urgency=UpdateUrgency.CURRENT,
            service_name="svc",
        )
        eng.register_dependency(
            package_name="pip-b",
            current_version="1.0",
            latest_version="1.0",
            ecosystem=DependencyEcosystem.PIP,
            urgency=UpdateUrgency.CURRENT,
            service_name="svc",
        )
        eng.register_dependency(
            package_name="pip-c",
            current_version="0.5",
            latest_version="2.0",
            ecosystem=DependencyEcosystem.PIP,
            urgency=UpdateUrgency.MAJOR_BEHIND,
            service_name="svc",
        )
        # NPM: 0 current out of 2
        eng.register_dependency(
            package_name="npm-a",
            current_version="1.0",
            latest_version="3.0",
            ecosystem=DependencyEcosystem.NPM,
            urgency=UpdateUrgency.END_OF_LIFE,
            service_name="svc",
        )
        eng.register_dependency(
            package_name="npm-b",
            current_version="1.0",
            latest_version="2.0",
            ecosystem=DependencyEcosystem.NPM,
            urgency=UpdateUrgency.MINOR_BEHIND,
            service_name="svc",
        )
        health = eng.analyze_ecosystem_health()
        assert len(health) == 2
        # Sorted by freshness_pct descending
        assert health[0]["ecosystem"] == "pip"
        assert health[0]["total_dependencies"] == 3
        assert health[0]["up_to_date_count"] == 2
        assert health[0]["freshness_pct"] == round(2 / 3 * 100, 2)
        assert health[1]["ecosystem"] == "npm"
        assert health[1]["freshness_pct"] == 0.0
        assert health[1]["eol_count"] == 1


# ===========================================================================
# GenerateFreshnessReport
# ===========================================================================


class TestGenerateFreshnessReport:
    """Test DependencyFreshnessMonitor.generate_freshness_report."""

    def test_basic_report(self):
        eng = _engine(stale_version_threshold=1)
        eng.register_dependency(
            package_name="pkg-current",
            current_version="1.0",
            latest_version="1.0",
            urgency=UpdateUrgency.CURRENT,
            ecosystem=DependencyEcosystem.PIP,
            service_name="svc-a",
        )
        eng.register_dependency(
            package_name="pkg-eol",
            current_version="0.1",
            latest_version="3.0",
            urgency=UpdateUrgency.END_OF_LIFE,
            ecosystem=DependencyEcosystem.NPM,
            service_name="svc-b",
        )
        eng.register_dependency(
            package_name="pkg-sec",
            current_version="1.0",
            latest_version="1.1",
            urgency=UpdateUrgency.SECURITY_UPDATE,
            has_security_advisory=True,
            ecosystem=DependencyEcosystem.PIP,
            service_name="svc-a",
        )
        report = eng.generate_freshness_report()
        assert isinstance(report, FreshnessReport)
        assert report.total_dependencies == 3
        assert report.total_services == 2
        assert report.eol_count == 1
        assert report.security_update_count >= 1
        assert report.generated_at > 0
        assert len(report.ecosystem_distribution) >= 1
        assert len(report.recommendations) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test DependencyFreshnessMonitor.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.register_dependency(
            package_name="pkg-x",
            current_version="1.0",
            latest_version="1.0",
            service_name="svc",
        )
        eng.clear_data()
        assert len(eng.list_dependencies()) == 0
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test DependencyFreshnessMonitor.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 0
        assert stats["unique_services"] == 0
        assert stats["direct_count"] == 0
        assert stats["transitive_count"] == 0
        assert stats["ecosystem_distribution"] == {}
        assert stats["urgency_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.register_dependency(
            package_name="pkg-a",
            current_version="1.0",
            latest_version="1.0",
            ecosystem=DependencyEcosystem.PIP,
            urgency=UpdateUrgency.CURRENT,
            service_name="svc-a",
            is_direct=True,
        )
        eng.register_dependency(
            package_name="pkg-b",
            current_version="0.5",
            latest_version="2.0",
            ecosystem=DependencyEcosystem.NPM,
            urgency=UpdateUrgency.MAJOR_BEHIND,
            service_name="svc-b",
            is_direct=False,
        )
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 2
        assert stats["unique_services"] == 2
        assert stats["direct_count"] == 1
        assert stats["transitive_count"] == 1
        assert stats["ecosystem_distribution"]["pip"] == 1
        assert stats["ecosystem_distribution"]["npm"] == 1
        assert stats["urgency_distribution"]["current"] == 1
        assert stats["urgency_distribution"]["major_behind"] == 1

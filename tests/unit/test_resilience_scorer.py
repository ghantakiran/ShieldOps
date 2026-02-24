"""Tests for shieldops.observability.resilience_scorer — ResilienceScoreCalculator."""

from __future__ import annotations

from shieldops.observability.resilience_scorer import (
    RecoveryCapability,
    RedundancyLevel,
    ResilienceGrade,
    ResilienceReport,
    ResilienceScore,
    ResilienceScoreCalculator,
    ServiceResilienceProfile,
)


def _engine(**kw) -> ResilienceScoreCalculator:
    return ResilienceScoreCalculator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ResilienceGrade (5)
    def test_grade_excellent(self):
        assert ResilienceGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert ResilienceGrade.GOOD == "good"

    def test_grade_fair(self):
        assert ResilienceGrade.FAIR == "fair"

    def test_grade_poor(self):
        assert ResilienceGrade.POOR == "poor"

    def test_grade_critical(self):
        assert ResilienceGrade.CRITICAL == "critical"

    # RedundancyLevel (5)
    def test_redundancy_none(self):
        assert RedundancyLevel.NONE == "none"

    def test_redundancy_single(self):
        assert RedundancyLevel.SINGLE == "single"

    def test_redundancy_active_passive(self):
        assert RedundancyLevel.ACTIVE_PASSIVE == "active_passive"

    def test_redundancy_active_active(self):
        assert RedundancyLevel.ACTIVE_ACTIVE == "active_active"

    def test_redundancy_multi_region(self):
        assert RedundancyLevel.MULTI_REGION == "multi_region"

    # RecoveryCapability (5)
    def test_recovery_manual(self):
        assert RecoveryCapability.MANUAL == "manual"

    def test_recovery_semi_automated(self):
        assert RecoveryCapability.SEMI_AUTOMATED == "semi_automated"

    def test_recovery_fully_automated(self):
        assert RecoveryCapability.FULLY_AUTOMATED == "fully_automated"

    def test_recovery_self_healing(self):
        assert RecoveryCapability.SELF_HEALING == "self_healing"

    def test_recovery_chaos_tested(self):
        assert RecoveryCapability.CHAOS_TESTED == "chaos_tested"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_profile_defaults(self):
        p = ServiceResilienceProfile()
        assert p.id
        assert p.service_name == ""
        assert p.redundancy_level == RedundancyLevel.NONE
        assert p.recovery_capability == RecoveryCapability.MANUAL
        assert p.mttr_minutes == 0.0
        assert p.blast_radius_pct == 0.0
        assert p.has_circuit_breaker is False
        assert p.has_fallback is False
        assert p.last_incident_days_ago == 0

    def test_score_defaults(self):
        s = ResilienceScore()
        assert s.id
        assert s.service_id == ""
        assert s.service_name == ""
        assert s.overall_score == 0.0
        assert s.grade == ResilienceGrade.CRITICAL
        assert s.redundancy_score == 0.0
        assert s.recovery_score == 0.0
        assert s.blast_radius_score == 0.0
        assert s.protection_score == 0.0
        assert s.recommendations == []

    def test_report_defaults(self):
        r = ResilienceReport()
        assert r.total_profiles == 0
        assert r.avg_score == 0.0
        assert r.grade_distribution == {}
        assert r.weakest_services == []
        assert r.top_recommendations == []


# ---------------------------------------------------------------------------
# register_profile
# ---------------------------------------------------------------------------


class TestRegisterProfile:
    def test_basic_register(self):
        eng = _engine()
        p = eng.register_profile(
            service_name="payment-api",
            redundancy_level=RedundancyLevel.ACTIVE_ACTIVE,
            recovery_capability=RecoveryCapability.SELF_HEALING,
            mttr_minutes=15.0,
            blast_radius_pct=10.0,
            has_circuit_breaker=True,
            has_fallback=True,
            last_incident_days_ago=90,
        )
        assert p.service_name == "payment-api"
        assert p.redundancy_level == RedundancyLevel.ACTIVE_ACTIVE
        assert p.recovery_capability == RecoveryCapability.SELF_HEALING
        assert p.mttr_minutes == 15.0
        assert p.blast_radius_pct == 10.0
        assert p.has_circuit_breaker is True
        assert p.has_fallback is True
        assert p.last_incident_days_ago == 90

    def test_eviction_at_max(self):
        eng = _engine(max_profiles=3)
        for i in range(5):
            eng.register_profile(service_name=f"svc-{i}")
        assert len(eng._profiles) == 3


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_found(self):
        eng = _engine()
        p = eng.register_profile(service_name="auth-service")
        assert eng.get_profile(p.id) is not None
        assert eng.get_profile(p.id).service_name == "auth-service"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_profile("nonexistent") is None


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_list_all(self):
        eng = _engine()
        eng.register_profile(service_name="a")
        eng.register_profile(service_name="b")
        assert len(eng.list_profiles()) == 2

    def test_filter_by_redundancy(self):
        eng = _engine()
        eng.register_profile(service_name="a", redundancy_level=RedundancyLevel.MULTI_REGION)
        eng.register_profile(service_name="b", redundancy_level=RedundancyLevel.NONE)
        results = eng.list_profiles(redundancy_level=RedundancyLevel.MULTI_REGION)
        assert len(results) == 1
        assert results[0].service_name == "a"

    def test_filter_by_recovery(self):
        eng = _engine()
        eng.register_profile(service_name="a", recovery_capability=RecoveryCapability.CHAOS_TESTED)
        eng.register_profile(service_name="b", recovery_capability=RecoveryCapability.MANUAL)
        results = eng.list_profiles(recovery_capability=RecoveryCapability.CHAOS_TESTED)
        assert len(results) == 1
        assert results[0].service_name == "a"


# ---------------------------------------------------------------------------
# calculate_score
# ---------------------------------------------------------------------------


class TestCalculateScore:
    def test_high_score(self):
        eng = _engine()
        p = eng.register_profile(
            service_name="resilient-svc",
            redundancy_level=RedundancyLevel.MULTI_REGION,
            recovery_capability=RecoveryCapability.CHAOS_TESTED,
            blast_radius_pct=5.0,
            has_circuit_breaker=True,
            has_fallback=True,
            last_incident_days_ago=90,
        )
        score = eng.calculate_score(p.id)
        assert score.service_name == "resilient-svc"
        # multi_region=100, chaos_tested=100, blast_radius=95, protection=100 -> 98.75
        assert score.overall_score >= 90.0
        assert score.grade == ResilienceGrade.EXCELLENT
        assert score.redundancy_score == 100.0
        assert score.recovery_score == 100.0

    def test_low_score(self):
        eng = _engine()
        p = eng.register_profile(
            service_name="fragile-svc",
            redundancy_level=RedundancyLevel.NONE,
            recovery_capability=RecoveryCapability.MANUAL,
            blast_radius_pct=80.0,
            has_circuit_breaker=False,
            has_fallback=False,
            last_incident_days_ago=0,
        )
        score = eng.calculate_score(p.id)
        assert score.service_name == "fragile-svc"
        # none=0, manual=0, blast_radius=20, protection=0 -> 5.0
        assert score.overall_score < 40.0
        assert score.grade == ResilienceGrade.CRITICAL
        assert score.redundancy_score == 0.0
        assert score.recovery_score == 0.0
        assert len(score.recommendations) >= 1


# ---------------------------------------------------------------------------
# calculate_all_scores
# ---------------------------------------------------------------------------


class TestCalculateAllScores:
    def test_multiple_services(self):
        eng = _engine()
        eng.register_profile(service_name="good", redundancy_level=RedundancyLevel.ACTIVE_ACTIVE)
        eng.register_profile(service_name="bad", redundancy_level=RedundancyLevel.NONE)
        scores = eng.calculate_all_scores()
        assert len(scores) == 2
        names = {s.service_name for s in scores}
        assert "good" in names
        assert "bad" in names


# ---------------------------------------------------------------------------
# identify_weakest_links
# ---------------------------------------------------------------------------


class TestIdentifyWeakestLinks:
    def test_with_weak_links_below_threshold(self):
        eng = _engine(minimum_score_threshold=60.0)
        eng.register_profile(
            service_name="strong",
            redundancy_level=RedundancyLevel.MULTI_REGION,
            recovery_capability=RecoveryCapability.CHAOS_TESTED,
            blast_radius_pct=5.0,
            has_circuit_breaker=True,
            has_fallback=True,
            last_incident_days_ago=90,
        )
        eng.register_profile(
            service_name="weak",
            redundancy_level=RedundancyLevel.NONE,
            recovery_capability=RecoveryCapability.MANUAL,
            blast_radius_pct=80.0,
        )
        weak = eng.identify_weakest_links()
        assert len(weak) >= 1
        assert weak[0].service_name == "weak"
        assert weak[0].overall_score < 60.0


# ---------------------------------------------------------------------------
# compare_services
# ---------------------------------------------------------------------------


class TestCompareServices:
    def test_compare_two_services(self):
        eng = _engine()
        p1 = eng.register_profile(
            service_name="premium",
            redundancy_level=RedundancyLevel.MULTI_REGION,
            recovery_capability=RecoveryCapability.CHAOS_TESTED,
        )
        p2 = eng.register_profile(
            service_name="basic",
            redundancy_level=RedundancyLevel.NONE,
            recovery_capability=RecoveryCapability.MANUAL,
        )
        compared = eng.compare_services([p1.id, p2.id])
        assert len(compared) == 2
        # Sorted descending by overall_score — premium should be first
        assert compared[0].service_name == "premium"
        assert compared[0].overall_score >= compared[1].overall_score


# ---------------------------------------------------------------------------
# recommend_improvements
# ---------------------------------------------------------------------------


class TestRecommendImprovements:
    def test_service_with_deficiencies(self):
        eng = _engine()
        p = eng.register_profile(
            service_name="needs-work",
            redundancy_level=RedundancyLevel.NONE,
            recovery_capability=RecoveryCapability.MANUAL,
            blast_radius_pct=80.0,
            has_circuit_breaker=False,
            has_fallback=False,
            mttr_minutes=120.0,
        )
        recs = eng.recommend_improvements(p.id)
        assert len(recs) >= 3
        # Should mention redundancy, recovery, blast radius, circuit breaker, fallback, MTTR
        combined = " ".join(recs).lower()
        assert "redundancy" in combined
        assert "circuit breaker" in combined
        assert "fallback" in combined


# ---------------------------------------------------------------------------
# generate_resilience_report
# ---------------------------------------------------------------------------


class TestGenerateResilienceReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_profile(
            service_name="svc-a",
            redundancy_level=RedundancyLevel.ACTIVE_ACTIVE,
            recovery_capability=RecoveryCapability.FULLY_AUTOMATED,
        )
        eng.register_profile(
            service_name="svc-b",
            redundancy_level=RedundancyLevel.NONE,
            recovery_capability=RecoveryCapability.MANUAL,
        )
        report = eng.generate_resilience_report()
        assert report.total_profiles == 2
        assert report.avg_score > 0.0
        assert isinstance(report.grade_distribution, dict)
        assert len(report.grade_distribution) >= 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_lists(self):
        eng = _engine()
        p = eng.register_profile(service_name="svc")
        eng.calculate_score(p.id)
        assert len(eng._profiles) > 0
        assert len(eng._scores) > 0
        eng.clear_data()
        assert len(eng._profiles) == 0
        assert len(eng._scores) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_profiles"] == 0
        assert stats["total_scores"] == 0
        assert stats["unique_service_names"] == 0
        assert stats["redundancy_levels"] == []
        assert stats["recovery_capabilities"] == []

    def test_populated(self):
        eng = _engine()
        eng.register_profile(
            service_name="api",
            redundancy_level=RedundancyLevel.ACTIVE_ACTIVE,
            recovery_capability=RecoveryCapability.SELF_HEALING,
        )
        eng.register_profile(
            service_name="db",
            redundancy_level=RedundancyLevel.NONE,
            recovery_capability=RecoveryCapability.MANUAL,
        )
        stats = eng.get_stats()
        assert stats["total_profiles"] == 2
        assert stats["unique_service_names"] == 2
        assert "active_active" in stats["redundancy_levels"]
        assert "none" in stats["redundancy_levels"]
        assert "self_healing" in stats["recovery_capabilities"]
        assert "manual" in stats["recovery_capabilities"]

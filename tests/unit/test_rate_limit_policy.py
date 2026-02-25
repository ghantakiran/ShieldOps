"""Tests for shieldops.topology.rate_limit_policy — RateLimitPolicyManager."""

from __future__ import annotations

from shieldops.topology.rate_limit_policy import (
    PolicyEffectiveness,
    PolicyScope,
    RateLimitPolicyManager,
    RateLimitPolicyRecord,
    RateLimitPolicyReport,
    RateLimitViolation,
    ViolationType,
)


def _engine(**kw) -> RateLimitPolicyManager:
    return RateLimitPolicyManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PolicyScope (5)
    def test_scope_service(self):
        assert PolicyScope.SERVICE == "service"

    def test_scope_endpoint(self):
        assert PolicyScope.ENDPOINT == "endpoint"

    def test_scope_consumer(self):
        assert PolicyScope.CONSUMER == "consumer"

    def test_scope_global(self):
        assert PolicyScope.GLOBAL == "global"

    def test_scope_tenant(self):
        assert PolicyScope.TENANT == "tenant"

    # ViolationType (5)
    def test_violation_soft_limit(self):
        assert ViolationType.SOFT_LIMIT == "soft_limit"

    def test_violation_hard_limit(self):
        assert ViolationType.HARD_LIMIT == "hard_limit"

    def test_violation_burst(self):
        assert ViolationType.BURST == "burst"

    def test_violation_sustained(self):
        assert ViolationType.SUSTAINED == "sustained"

    def test_violation_cascading(self):
        assert ViolationType.CASCADING == "cascading"

    # PolicyEffectiveness (5)
    def test_effectiveness_optimal(self):
        assert PolicyEffectiveness.OPTIMAL == "optimal"

    def test_effectiveness_conservative(self):
        assert PolicyEffectiveness.CONSERVATIVE == "conservative"

    def test_effectiveness_aggressive(self):
        assert PolicyEffectiveness.AGGRESSIVE == "aggressive"

    def test_effectiveness_ineffective(self):
        assert PolicyEffectiveness.INEFFECTIVE == "ineffective"

    def test_effectiveness_untuned(self):
        assert PolicyEffectiveness.UNTUNED == "untuned"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_rate_limit_policy_record_defaults(self):
        r = RateLimitPolicyRecord()
        assert r.id
        assert r.service_name == ""
        assert r.scope == PolicyScope.SERVICE
        assert r.requests_per_second == 0
        assert r.burst_limit == 0
        assert r.effectiveness == PolicyEffectiveness.UNTUNED
        assert r.details == ""
        assert r.created_at > 0

    def test_rate_limit_violation_defaults(self):
        r = RateLimitViolation()
        assert r.id
        assert r.service_name == ""
        assert r.violation_type == ViolationType.SOFT_LIMIT
        assert r.count == 0
        assert r.consumer == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_rate_limit_policy_report_defaults(self):
        r = RateLimitPolicyReport()
        assert r.total_policies == 0
        assert r.total_violations == 0
        assert r.avg_requests_per_second == 0.0
        assert r.by_scope == {}
        assert r.by_effectiveness == {}
        assert r.untuned_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_policy
# -------------------------------------------------------------------


class TestRecordPolicy:
    def test_basic(self):
        eng = _engine()
        r = eng.record_policy("auth-svc", requests_per_second=500, burst_limit=1000)
        assert r.service_name == "auth-svc"
        assert r.requests_per_second == 500
        assert r.burst_limit == 1000
        assert r.scope == PolicyScope.SERVICE

    def test_with_scope_and_effectiveness(self):
        eng = _engine()
        r = eng.record_policy(
            "api-gateway",
            scope=PolicyScope.ENDPOINT,
            effectiveness=PolicyEffectiveness.OPTIMAL,
        )
        assert r.scope == PolicyScope.ENDPOINT
        assert r.effectiveness == PolicyEffectiveness.OPTIMAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_policy(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_policy
# -------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        eng = _engine()
        r = eng.record_policy("auth-svc")
        assert eng.get_policy(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


# -------------------------------------------------------------------
# list_policies
# -------------------------------------------------------------------


class TestListPolicies:
    def test_list_all(self):
        eng = _engine()
        eng.record_policy("svc-a")
        eng.record_policy("svc-b")
        assert len(eng.list_policies()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_policy("svc-a")
        eng.record_policy("svc-b")
        results = eng.list_policies(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_policy("svc-a", scope=PolicyScope.SERVICE)
        eng.record_policy("svc-b", scope=PolicyScope.ENDPOINT)
        results = eng.list_policies(scope=PolicyScope.ENDPOINT)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# record_violation
# -------------------------------------------------------------------


class TestRecordViolation:
    def test_basic(self):
        eng = _engine()
        v = eng.record_violation("auth-svc", count=50, consumer="client-x")
        assert v.service_name == "auth-svc"
        assert v.count == 50
        assert v.consumer == "client-x"
        assert v.violation_type == ViolationType.SOFT_LIMIT

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_violation(f"svc-{i}")
        assert len(eng._violations) == 2


# -------------------------------------------------------------------
# analyze_policy_effectiveness
# -------------------------------------------------------------------


class TestAnalyzePolicyEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_policy(
            "svc-a", requests_per_second=100, effectiveness=PolicyEffectiveness.OPTIMAL
        )
        eng.record_policy(
            "svc-a", requests_per_second=200, effectiveness=PolicyEffectiveness.UNTUNED
        )
        result = eng.analyze_policy_effectiveness("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_policies"] == 2
        assert result["avg_requests_per_second"] == 150.0
        assert "optimal" in result["effectiveness_breakdown"]

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_policy_effectiveness("unknown")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_untuned_policies
# -------------------------------------------------------------------


class TestIdentifyUntunedPolicies:
    def test_with_untuned(self):
        eng = _engine()
        eng.record_policy("svc-a", effectiveness=PolicyEffectiveness.UNTUNED)
        eng.record_policy("svc-b", effectiveness=PolicyEffectiveness.OPTIMAL)
        results = eng.identify_untuned_policies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_untuned_policies() == []


# -------------------------------------------------------------------
# rank_most_violated_services
# -------------------------------------------------------------------


class TestRankMostViolatedServices:
    def test_with_data(self):
        eng = _engine()
        eng.record_violation("svc-a", count=50)
        eng.record_violation("svc-a", count=30)
        eng.record_violation("svc-b", count=100)
        results = eng.rank_most_violated_services()
        assert len(results) == 2
        # svc-b: 100, svc-a: 80 — sorted desc
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["total_violations"] == 100

    def test_empty(self):
        eng = _engine()
        assert eng.rank_most_violated_services() == []


# -------------------------------------------------------------------
# recommend_limit_adjustments
# -------------------------------------------------------------------


class TestRecommendLimitAdjustments:
    def test_above_threshold(self):
        eng = _engine(violation_threshold=100)
        eng.record_violation("svc-a", count=150)
        results = eng.recommend_limit_adjustments()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["recommendation"] == "increase_limit"

    def test_below_threshold(self):
        eng = _engine(violation_threshold=100)
        eng.record_violation("svc-a", count=50)
        results = eng.recommend_limit_adjustments()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.recommend_limit_adjustments() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(violation_threshold=10)
        eng.record_policy(
            "svc-a", requests_per_second=100, effectiveness=PolicyEffectiveness.UNTUNED
        )
        eng.record_violation("svc-a", count=50)
        report = eng.generate_report()
        assert report.total_policies == 1
        assert report.total_violations == 1
        assert report.untuned_count == 1
        assert report.by_scope != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_policies == 0
        assert "well-tuned" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_policy("svc-a")
        eng.record_violation("svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._violations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_violations"] == 0
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_policy("svc-a")
        eng.record_policy("svc-b")
        eng.record_violation("svc-a", count=10)
        stats = eng.get_stats()
        assert stats["total_policies"] == 2
        assert stats["total_violations"] == 1
        assert stats["unique_services"] == 2
        assert stats["violation_threshold"] == 100

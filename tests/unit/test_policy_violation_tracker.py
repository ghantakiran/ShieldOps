"""Tests for shieldops.compliance.policy_violation_tracker."""

from __future__ import annotations

from shieldops.compliance.policy_violation_tracker import (
    PolicyDomain,
    PolicyViolation,
    PolicyViolationTracker,
    ViolationReport,
    ViolationSeverity,
    ViolationTrend,
    ViolatorType,
)


def _engine(**kw) -> PolicyViolationTracker:
    return PolicyViolationTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ViolationSeverity (5 values)

    def test_severity_informational(self):
        assert ViolationSeverity.INFORMATIONAL == "informational"

    def test_severity_low(self):
        assert ViolationSeverity.LOW == "low"

    def test_severity_medium(self):
        assert ViolationSeverity.MEDIUM == "medium"

    def test_severity_high(self):
        assert ViolationSeverity.HIGH == "high"

    def test_severity_critical(self):
        assert ViolationSeverity.CRITICAL == "critical"

    # ViolatorType (5 values)

    def test_violator_agent(self):
        assert ViolatorType.AGENT == "agent"

    def test_violator_service(self):
        assert ViolatorType.SERVICE == "service"

    def test_violator_team(self):
        assert ViolatorType.TEAM == "team"

    def test_violator_automated_pipeline(self):
        assert ViolatorType.AUTOMATED_PIPELINE == "automated_pipeline"

    def test_violator_manual_user(self):
        assert ViolatorType.MANUAL_USER == "manual_user"

    # PolicyDomain (5 values)

    def test_domain_infrastructure(self):
        assert PolicyDomain.INFRASTRUCTURE == "infrastructure"

    def test_domain_data_access(self):
        assert PolicyDomain.DATA_ACCESS == "data_access"

    def test_domain_deployment(self):
        assert PolicyDomain.DEPLOYMENT == "deployment"

    def test_domain_security(self):
        assert PolicyDomain.SECURITY == "security"

    def test_domain_cost_control(self):
        assert PolicyDomain.COST_CONTROL == "cost_control"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_policy_violation_defaults(self):
        pv = PolicyViolation()
        assert pv.id
        assert pv.policy_name == ""
        assert pv.violator_name == ""
        assert pv.violator_type == ViolatorType.AGENT
        assert pv.severity == ViolationSeverity.LOW
        assert pv.domain == PolicyDomain.INFRASTRUCTURE
        assert pv.description == ""
        assert pv.resolved is False
        assert pv.created_at > 0

    def test_violation_trend_defaults(self):
        vt = ViolationTrend()
        assert vt.id
        assert vt.policy_name == ""
        assert vt.period_label == ""
        assert vt.violation_count == 0
        assert vt.severity_breakdown == {}
        assert vt.trend_direction == "stable"
        assert vt.created_at > 0

    def test_violation_report_defaults(self):
        vr = ViolationReport()
        assert vr.total_violations == 0
        assert vr.total_resolved == 0
        assert vr.total_unresolved == 0
        assert vr.by_severity == {}
        assert vr.by_domain == {}
        assert vr.by_violator_type == {}
        assert vr.repeat_offenders == []
        assert vr.recommendations == []
        assert vr.generated_at > 0


# -------------------------------------------------------------------
# record_violation
# -------------------------------------------------------------------


class TestRecordViolation:
    def test_basic_record(self):
        eng = _engine()
        v = eng.record_violation("no-root-access", "agent-x")
        assert v.policy_name == "no-root-access"
        assert v.violator_name == "agent-x"
        assert len(eng.list_violations()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        v1 = eng.record_violation("pol-a", "agent-1")
        v2 = eng.record_violation("pol-b", "agent-2")
        assert v1.id != v2.id

    def test_record_with_values(self):
        eng = _engine()
        v = eng.record_violation(
            "no-root-access",
            "agent-x",
            violator_type=ViolatorType.SERVICE,
            severity=ViolationSeverity.CRITICAL,
            domain=PolicyDomain.SECURITY,
            description="Attempted root access",
        )
        assert v.violator_type == ViolatorType.SERVICE
        assert v.severity == ViolationSeverity.CRITICAL
        assert v.domain == PolicyDomain.SECURITY
        assert v.description == "Attempted root access"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            v = eng.record_violation(f"pol-{i}", f"agent-{i}")
            ids.append(v.id)
        violations = eng.list_violations(limit=100)
        assert len(violations) == 3
        found = {v.id for v in violations}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_violation
# -------------------------------------------------------------------


class TestGetViolation:
    def test_get_existing(self):
        eng = _engine()
        v = eng.record_violation("pol-a", "agent-1")
        found = eng.get_violation(v.id)
        assert found is not None
        assert found.id == v.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_violation("nonexistent") is None


# -------------------------------------------------------------------
# list_violations
# -------------------------------------------------------------------


class TestListViolations:
    def test_list_all(self):
        eng = _engine()
        eng.record_violation("pol-a", "agent-1")
        eng.record_violation("pol-b", "agent-2")
        eng.record_violation("pol-c", "agent-3")
        assert len(eng.list_violations()) == 3

    def test_filter_by_policy(self):
        eng = _engine()
        eng.record_violation("pol-a", "agent-1")
        eng.record_violation("pol-b", "agent-2")
        eng.record_violation("pol-a", "agent-3")
        results = eng.list_violations(policy_name="pol-a")
        assert len(results) == 2
        assert all(v.policy_name == "pol-a" for v in results)

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_violation("pol-a", "agent-1", severity=ViolationSeverity.CRITICAL)
        eng.record_violation("pol-b", "agent-2", severity=ViolationSeverity.LOW)
        results = eng.list_violations(severity=ViolationSeverity.CRITICAL)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_violation(f"pol-{i}", f"agent-{i}")
        results = eng.list_violations(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# compute_trend
# -------------------------------------------------------------------


class TestComputeTrend:
    def test_basic_trend(self):
        eng = _engine()
        for _ in range(5):
            eng.record_violation("pol-a", "agent-1")
        trend = eng.compute_trend("pol-a")
        assert trend.policy_name == "pol-a"
        assert trend.violation_count == 5
        assert isinstance(trend.severity_breakdown, dict)

    def test_trend_no_violations(self):
        eng = _engine()
        trend = eng.compute_trend("pol-a")
        assert trend.violation_count == 0
        assert trend.trend_direction == "stable"


# -------------------------------------------------------------------
# list_trends
# -------------------------------------------------------------------


class TestListTrends:
    def test_list_all(self):
        eng = _engine()
        eng.compute_trend("pol-a")
        eng.compute_trend("pol-b")
        assert len(eng.list_trends()) == 2

    def test_filter_by_policy(self):
        eng = _engine()
        eng.compute_trend("pol-a")
        eng.compute_trend("pol-b")
        results = eng.list_trends(policy_name="pol-a")
        assert len(results) == 1
        assert results[0].policy_name == "pol-a"


# -------------------------------------------------------------------
# identify_repeat_offenders
# -------------------------------------------------------------------


class TestIdentifyRepeatOffenders:
    def test_offenders_found(self):
        eng = _engine(repeat_threshold=3)
        for _ in range(5):
            eng.record_violation("pol-a", "bad-agent")
        eng.record_violation("pol-a", "good-agent")
        offenders = eng.identify_repeat_offenders()
        assert len(offenders) == 1
        assert offenders[0]["violator_name"] == "bad-agent"
        assert offenders[0]["violation_count"] == 5

    def test_no_offenders(self):
        eng = _engine(repeat_threshold=10)
        eng.record_violation("pol-a", "agent-1")
        eng.record_violation("pol-a", "agent-2")
        assert eng.identify_repeat_offenders() == []


# -------------------------------------------------------------------
# get_policy_effectiveness
# -------------------------------------------------------------------


class TestGetPolicyEffectiveness:
    def test_effective_policy(self):
        eng = _engine()
        for _ in range(5):
            eng.record_violation("pol-a", "agent-1", resolved=True)
        result = eng.get_policy_effectiveness("pol-a")
        assert result["total_violations"] == 5
        assert result["effectiveness"] == "highly_effective"

    def test_no_violations(self):
        eng = _engine()
        result = eng.get_policy_effectiveness("pol-a")
        assert result["total_violations"] == 0
        assert result["effectiveness"] == "unknown"


# -------------------------------------------------------------------
# get_violator_profile
# -------------------------------------------------------------------


class TestGetViolatorProfile:
    def test_profile_found(self):
        eng = _engine()
        eng.record_violation("pol-a", "agent-x", severity=ViolationSeverity.HIGH)
        eng.record_violation("pol-b", "agent-x", severity=ViolationSeverity.LOW)
        result = eng.get_violator_profile("agent-x")
        assert result["found"] is True
        assert result["total_violations"] == 2
        assert "pol-a" in result["by_policy"]

    def test_profile_not_found(self):
        eng = _engine()
        result = eng.get_violator_profile("agent-x")
        assert result["found"] is False
        assert result["total_violations"] == 0


# -------------------------------------------------------------------
# generate_violation_report
# -------------------------------------------------------------------


class TestGenerateViolationReport:
    def test_basic_report(self):
        eng = _engine(repeat_threshold=2)
        eng.record_violation(
            "pol-a",
            "agent-1",
            severity=ViolationSeverity.CRITICAL,
        )
        eng.record_violation(
            "pol-b",
            "agent-1",
            severity=ViolationSeverity.LOW,
        )
        report = eng.generate_violation_report()
        assert report.total_violations == 2
        assert isinstance(report.by_severity, dict)
        assert isinstance(report.by_domain, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_violation_report()
        assert report.total_violations == 0
        assert report.total_resolved == 0
        assert report.total_unresolved == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_violation("pol-a", "agent-1")
        eng.record_violation("pol-b", "agent-2")
        eng.compute_trend("pol-a")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_violations()) == 0
        assert len(eng.list_trends()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_violations"] == 0
        assert stats["total_trends"] == 0
        assert stats["repeat_threshold"] == 5
        assert stats["severity_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_violation(
            "pol-a",
            "agent-1",
            severity=ViolationSeverity.HIGH,
        )
        eng.record_violation(
            "pol-b",
            "agent-2",
            severity=ViolationSeverity.LOW,
        )
        eng.compute_trend("pol-a")
        stats = eng.get_stats()
        assert stats["total_violations"] == 2
        assert stats["total_trends"] == 1
        assert len(stats["severity_distribution"]) == 2

"""Tests for shieldops.compliance.automated_policy_enforcer — AutomatedPolicyEnforcer."""

from __future__ import annotations

from shieldops.compliance.automated_policy_enforcer import (
    AutomatedPolicyEnforcer,
    EnforcementAction,
    EnforcementAnalysis,
    EnforcementRecord,
    EnforcementReport,
    EnforcementScope,
    ViolationSeverity,
)


def _engine(**kw) -> AutomatedPolicyEnforcer:
    return AutomatedPolicyEnforcer(**kw)


class TestEnums:
    def test_action_block(self):
        assert EnforcementAction.BLOCK == "block"

    def test_action_alert(self):
        assert EnforcementAction.ALERT == "alert"

    def test_action_remediate(self):
        assert EnforcementAction.REMEDIATE == "remediate"

    def test_action_audit(self):
        assert EnforcementAction.AUDIT == "audit"

    def test_action_exempt(self):
        assert EnforcementAction.EXEMPT == "exempt"

    def test_scope_realtime(self):
        assert EnforcementScope.REALTIME == "realtime"

    def test_scope_scheduled(self):
        assert EnforcementScope.SCHEDULED == "scheduled"

    def test_scope_on_demand(self):
        assert EnforcementScope.ON_DEMAND == "on_demand"

    def test_scope_continuous(self):
        assert EnforcementScope.CONTINUOUS == "continuous"

    def test_scope_event_driven(self):
        assert EnforcementScope.EVENT_DRIVEN == "event_driven"

    def test_severity_critical(self):
        assert ViolationSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ViolationSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert ViolationSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert ViolationSeverity.LOW == "low"

    def test_severity_informational(self):
        assert ViolationSeverity.INFORMATIONAL == "informational"


class TestModels:
    def test_record_defaults(self):
        r = EnforcementRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.enforcement_action == EnforcementAction.BLOCK
        assert r.enforcement_scope == EnforcementScope.REALTIME
        assert r.violation_severity == ViolationSeverity.CRITICAL
        assert r.enforcement_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = EnforcementAnalysis()
        assert a.id
        assert a.policy_name == ""
        assert a.enforcement_action == EnforcementAction.BLOCK
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = EnforcementReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_enforcement_score == 0.0
        assert r.by_action == {}
        assert r.by_scope == {}
        assert r.by_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_enforcement(
            policy_name="block-unencrypted",
            enforcement_action=EnforcementAction.BLOCK,
            enforcement_scope=EnforcementScope.CONTINUOUS,
            violation_severity=ViolationSeverity.HIGH,
            enforcement_score=85.0,
            service="policy-svc",
            team="compliance",
        )
        assert r.policy_name == "block-unencrypted"
        assert r.enforcement_action == EnforcementAction.BLOCK
        assert r.enforcement_score == 85.0
        assert r.service == "policy-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_enforcement(policy_name=f"enf-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_enforcement(policy_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_enforcement(policy_name="a")
        eng.record_enforcement(policy_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enforcement_action(self):
        eng = _engine()
        eng.record_enforcement(policy_name="a", enforcement_action=EnforcementAction.BLOCK)
        eng.record_enforcement(policy_name="b", enforcement_action=EnforcementAction.ALERT)
        assert len(eng.list_records(enforcement_action=EnforcementAction.BLOCK)) == 1

    def test_filter_by_violation_severity(self):
        eng = _engine()
        eng.record_enforcement(policy_name="a", violation_severity=ViolationSeverity.CRITICAL)
        eng.record_enforcement(policy_name="b", violation_severity=ViolationSeverity.LOW)
        assert len(eng.list_records(violation_severity=ViolationSeverity.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_enforcement(policy_name="a", team="sec")
        eng.record_enforcement(policy_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_enforcement(policy_name=f"e-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            policy_name="test",
            analysis_score=88.5,
            breached=True,
            description="policy violation",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(policy_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement(
            policy_name="a",
            enforcement_action=EnforcementAction.BLOCK,
            enforcement_score=90.0,
        )
        eng.record_enforcement(
            policy_name="b",
            enforcement_action=EnforcementAction.BLOCK,
            enforcement_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "block" in result
        assert result["block"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_enforcement(policy_name="a", enforcement_score=60.0)
        eng.record_enforcement(policy_name="b", enforcement_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_enforcement(policy_name="a", enforcement_score=50.0)
        eng.record_enforcement(policy_name="b", enforcement_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["enforcement_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_enforcement(policy_name="a", service="auth", enforcement_score=90.0)
        eng.record_enforcement(policy_name="b", service="api", enforcement_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(policy_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(policy_name="a", analysis_score=20.0)
        eng.add_analysis(policy_name="b", analysis_score=20.0)
        eng.add_analysis(policy_name="c", analysis_score=80.0)
        eng.add_analysis(policy_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_enforcement(policy_name="test", enforcement_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_enforcement(policy_name="test")
        eng.add_analysis(policy_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_enforcement(policy_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

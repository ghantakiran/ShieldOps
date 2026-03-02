"""Tests for shieldops.analytics.privilege_behavior_monitor — PrivilegeBehaviorMonitor."""

from __future__ import annotations

from shieldops.analytics.privilege_behavior_monitor import (
    BehaviorPattern,
    MonitoringStatus,
    PrivilegeAnalysis,
    PrivilegeBehaviorMonitor,
    PrivilegeBehaviorReport,
    PrivilegeRecord,
    PrivilegeType,
)


def _engine(**kw) -> PrivilegeBehaviorMonitor:
    return PrivilegeBehaviorMonitor(**kw)


class TestEnums:
    def test_privilege_admin(self):
        assert PrivilegeType.ADMIN == "admin"

    def test_privilege_elevated(self):
        assert PrivilegeType.ELEVATED == "elevated"

    def test_privilege_standard(self):
        assert PrivilegeType.STANDARD == "standard"

    def test_privilege_root(self):
        assert PrivilegeType.ROOT == "root"

    def test_privilege_service_account(self):
        assert PrivilegeType.SERVICE_ACCOUNT == "service_account"

    def test_pattern_normal_use(self):
        assert BehaviorPattern.NORMAL_USE == "normal_use"

    def test_pattern_privilege_escalation(self):
        assert BehaviorPattern.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_pattern_lateral_movement(self):
        assert BehaviorPattern.LATERAL_MOVEMENT == "lateral_movement"

    def test_pattern_data_hoarding(self):
        assert BehaviorPattern.DATA_HOARDING == "data_hoarding"

    def test_pattern_policy_bypass(self):
        assert BehaviorPattern.POLICY_BYPASS == "policy_bypass"

    def test_status_active(self):
        assert MonitoringStatus.ACTIVE == "active"

    def test_status_alerting(self):
        assert MonitoringStatus.ALERTING == "alerting"

    def test_status_investigating(self):
        assert MonitoringStatus.INVESTIGATING == "investigating"

    def test_status_resolved(self):
        assert MonitoringStatus.RESOLVED == "resolved"

    def test_status_baseline(self):
        assert MonitoringStatus.BASELINE == "baseline"


class TestModels:
    def test_record_defaults(self):
        r = PrivilegeRecord()
        assert r.id
        assert r.account_name == ""
        assert r.privilege_type == PrivilegeType.STANDARD
        assert r.behavior_pattern == BehaviorPattern.NORMAL_USE
        assert r.monitoring_status == MonitoringStatus.BASELINE
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PrivilegeAnalysis()
        assert a.id
        assert a.account_name == ""
        assert a.privilege_type == PrivilegeType.STANDARD
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PrivilegeBehaviorReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_privilege_type == {}
        assert r.by_behavior_pattern == {}
        assert r.by_monitoring_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_privilege(
            account_name="root-access",
            privilege_type=PrivilegeType.ELEVATED,
            behavior_pattern=BehaviorPattern.LATERAL_MOVEMENT,
            monitoring_status=MonitoringStatus.ALERTING,
            risk_score=85.0,
            service="iam-svc",
            team="security",
        )
        assert r.account_name == "root-access"
        assert r.privilege_type == PrivilegeType.ELEVATED
        assert r.risk_score == 85.0
        assert r.service == "iam-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_privilege(account_name=f"priv-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_privilege(account_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_privilege(account_name="a")
        eng.record_privilege(account_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_privilege_type(self):
        eng = _engine()
        eng.record_privilege(account_name="a", privilege_type=PrivilegeType.ADMIN)
        eng.record_privilege(account_name="b", privilege_type=PrivilegeType.STANDARD)
        assert len(eng.list_records(privilege_type=PrivilegeType.ADMIN)) == 1

    def test_filter_by_behavior_pattern(self):
        eng = _engine()
        eng.record_privilege(account_name="a", behavior_pattern=BehaviorPattern.NORMAL_USE)
        eng.record_privilege(account_name="b", behavior_pattern=BehaviorPattern.LATERAL_MOVEMENT)
        assert len(eng.list_records(behavior_pattern=BehaviorPattern.NORMAL_USE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_privilege(account_name="a", team="sec")
        eng.record_privilege(account_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_privilege(account_name=f"p-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            account_name="test",
            analysis_score=88.5,
            breached=True,
            description="escalation detected",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(account_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_privilege(account_name="a", privilege_type=PrivilegeType.ADMIN, risk_score=90.0)
        eng.record_privilege(account_name="b", privilege_type=PrivilegeType.ADMIN, risk_score=70.0)
        result = eng.analyze_distribution()
        assert "admin" in result
        assert result["admin"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_privilege(account_name="a", risk_score=60.0)
        eng.record_privilege(account_name="b", risk_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_privilege(account_name="a", risk_score=50.0)
        eng.record_privilege(account_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_privilege(account_name="a", service="auth", risk_score=90.0)
        eng.record_privilege(account_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(account_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(account_name="a", analysis_score=20.0)
        eng.add_analysis(account_name="b", analysis_score=20.0)
        eng.add_analysis(account_name="c", analysis_score=80.0)
        eng.add_analysis(account_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_privilege(account_name="test", risk_score=50.0)
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
        eng.record_privilege(account_name="test")
        eng.add_analysis(account_name="test")
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
        eng.record_privilege(account_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

"""Tests for shieldops.analytics.entity_behavior_profiler — EntityBehaviorProfiler."""

from __future__ import annotations

from shieldops.analytics.entity_behavior_profiler import (
    BehaviorAnalysis,
    BehaviorCategory,
    BehaviorProfileReport,
    BehaviorRecord,
    EntityBehaviorProfiler,
    EntityType,
    ProfileStatus,
)


def _engine(**kw) -> EntityBehaviorProfiler:
    return EntityBehaviorProfiler(**kw)


class TestEnums:
    def test_entity_user(self):
        assert EntityType.USER == "user"

    def test_entity_service_account(self):
        assert EntityType.SERVICE_ACCOUNT == "service_account"

    def test_entity_device(self):
        assert EntityType.DEVICE == "device"

    def test_entity_application(self):
        assert EntityType.APPLICATION == "application"

    def test_entity_network_segment(self):
        assert EntityType.NETWORK_SEGMENT == "network_segment"

    def test_behavior_authentication(self):
        assert BehaviorCategory.AUTHENTICATION == "authentication"

    def test_behavior_data_access(self):
        assert BehaviorCategory.DATA_ACCESS == "data_access"

    def test_behavior_network_activity(self):
        assert BehaviorCategory.NETWORK_ACTIVITY == "network_activity"

    def test_behavior_privilege_use(self):
        assert BehaviorCategory.PRIVILEGE_USE == "privilege_use"

    def test_behavior_resource_consumption(self):
        assert BehaviorCategory.RESOURCE_CONSUMPTION == "resource_consumption"

    def test_profile_baseline(self):
        assert ProfileStatus.BASELINE == "baseline"

    def test_profile_normal(self):
        assert ProfileStatus.NORMAL == "normal"

    def test_profile_anomalous(self):
        assert ProfileStatus.ANOMALOUS == "anomalous"

    def test_profile_suspicious(self):
        assert ProfileStatus.SUSPICIOUS == "suspicious"

    def test_profile_compromised(self):
        assert ProfileStatus.COMPROMISED == "compromised"


class TestModels:
    def test_record_defaults(self):
        r = BehaviorRecord()
        assert r.id
        assert r.entity_name == ""
        assert r.entity_type == EntityType.USER
        assert r.behavior_category == BehaviorCategory.AUTHENTICATION
        assert r.profile_status == ProfileStatus.BASELINE
        assert r.behavior_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = BehaviorAnalysis()
        assert a.id
        assert a.entity_name == ""
        assert a.entity_type == EntityType.USER
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = BehaviorProfileReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_behavior_score == 0.0
        assert r.by_entity_type == {}
        assert r.by_behavior_category == {}
        assert r.by_profile_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_behavior(
            entity_name="user-admin",
            entity_type=EntityType.SERVICE_ACCOUNT,
            behavior_category=BehaviorCategory.PRIVILEGE_USE,
            profile_status=ProfileStatus.ANOMALOUS,
            behavior_score=85.0,
            service="auth-svc",
            team="security",
        )
        assert r.entity_name == "user-admin"
        assert r.entity_type == EntityType.SERVICE_ACCOUNT
        assert r.behavior_score == 85.0
        assert r.service == "auth-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_behavior(entity_name=f"user-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_behavior(entity_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_behavior(entity_name="a")
        eng.record_behavior(entity_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_entity_type(self):
        eng = _engine()
        eng.record_behavior(entity_name="a", entity_type=EntityType.USER)
        eng.record_behavior(entity_name="b", entity_type=EntityType.DEVICE)
        assert len(eng.list_records(entity_type=EntityType.USER)) == 1

    def test_filter_by_behavior_category(self):
        eng = _engine()
        eng.record_behavior(entity_name="a", behavior_category=BehaviorCategory.AUTHENTICATION)
        eng.record_behavior(entity_name="b", behavior_category=BehaviorCategory.DATA_ACCESS)
        assert len(eng.list_records(behavior_category=BehaviorCategory.AUTHENTICATION)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_behavior(entity_name="a", team="sec")
        eng.record_behavior(entity_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_behavior(entity_name=f"u-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            entity_name="test", analysis_score=88.5, breached=True, description="anomaly"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(entity_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_behavior(entity_name="a", entity_type=EntityType.USER, behavior_score=90.0)
        eng.record_behavior(entity_name="b", entity_type=EntityType.USER, behavior_score=70.0)
        result = eng.analyze_distribution()
        assert "user" in result
        assert result["user"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_behavior(entity_name="a", behavior_score=60.0)
        eng.record_behavior(entity_name="b", behavior_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_behavior(entity_name="a", behavior_score=50.0)
        eng.record_behavior(entity_name="b", behavior_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["behavior_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_behavior(entity_name="a", service="auth", behavior_score=90.0)
        eng.record_behavior(entity_name="b", service="api", behavior_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(entity_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(entity_name="a", analysis_score=20.0)
        eng.add_analysis(entity_name="b", analysis_score=20.0)
        eng.add_analysis(entity_name="c", analysis_score=80.0)
        eng.add_analysis(entity_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_behavior(entity_name="test", behavior_score=50.0)
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
        eng.record_behavior(entity_name="test")
        eng.add_analysis(entity_name="test")
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
        eng.record_behavior(entity_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1

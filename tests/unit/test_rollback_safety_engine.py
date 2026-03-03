"""Tests for shieldops.security.rollback_safety_engine — RollbackSafetyEngine."""

from __future__ import annotations

from shieldops.security.rollback_safety_engine import (
    RollbackAnalysis,
    RollbackRecord,
    RollbackReport,
    RollbackRisk,
    RollbackSafetyEngine,
    RollbackStatus,
    RollbackType,
)


def _engine(**kw) -> RollbackSafetyEngine:
    return RollbackSafetyEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_rollbacktype_val1(self):
        assert RollbackType.CONFIG_RESTORE == "config_restore"

    def test_rollbacktype_val2(self):
        assert RollbackType.DEPLOYMENT_ROLLBACK == "deployment_rollback"

    def test_rollbacktype_val3(self):
        assert RollbackType.PERMISSION_REVERT == "permission_revert"

    def test_rollbacktype_val4(self):
        assert RollbackType.NETWORK_RESTORE == "network_restore"

    def test_rollbacktype_val5(self):
        assert RollbackType.DATA_RECOVERY == "data_recovery"

    def test_rollbackrisk_val1(self):
        assert RollbackRisk.CRITICAL == "critical"

    def test_rollbackrisk_val2(self):
        assert RollbackRisk.HIGH == "high"

    def test_rollbackrisk_val3(self):
        assert RollbackRisk.MEDIUM == "medium"

    def test_rollbackrisk_val4(self):
        assert RollbackRisk.LOW == "low"

    def test_rollbackrisk_val5(self):
        assert RollbackRisk.MINIMAL == "minimal"

    def test_rollbackstatus_val1(self):
        assert RollbackStatus.PLANNED == "planned"

    def test_rollbackstatus_val2(self):
        assert RollbackStatus.EXECUTING == "executing"

    def test_rollbackstatus_val3(self):
        assert RollbackStatus.COMPLETED == "completed"

    def test_rollbackstatus_val4(self):
        assert RollbackStatus.FAILED == "failed"

    def test_rollbackstatus_val5(self):
        assert RollbackStatus.ABORTED == "aborted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = RollbackRecord()
        assert r.id
        assert r.name == ""
        assert r.rollback_type == RollbackType.CONFIG_RESTORE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = RollbackAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = RollbackReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_type == {}
        assert r.by_risk == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rollback(
            name="test",
            rollback_type=RollbackType.DEPLOYMENT_ROLLBACK,
            score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.name == "test"
        assert r.rollback_type == RollbackType.DEPLOYMENT_ROLLBACK
        assert r.score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rollback(name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_rollback(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_rollback(name="a")
        eng.record_rollback(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_rollback(name="a", rollback_type=RollbackType.CONFIG_RESTORE)
        eng.record_rollback(name="b", rollback_type=RollbackType.DEPLOYMENT_ROLLBACK)
        results = eng.list_records(rollback_type=RollbackType.CONFIG_RESTORE)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_rollback(name="a", rollback_risk=RollbackRisk.CRITICAL)
        eng.record_rollback(name="b", rollback_risk=RollbackRisk.HIGH)
        results = eng.list_records(rollback_risk=RollbackRisk.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_rollback(name="a", team="sec")
        eng.record_rollback(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rollback(name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_rollback(
            name="a",
            rollback_type=RollbackType.CONFIG_RESTORE,
            score=90.0,
        )
        eng.record_rollback(
            name="b",
            rollback_type=RollbackType.CONFIG_RESTORE,
            score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "config_restore" in result
        assert result["config_restore"]["count"] == 2
        assert result["config_restore"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(score_threshold=80.0)
        eng.record_rollback(name="a", score=60.0)
        eng.record_rollback(name="b", score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(score_threshold=80.0)
        eng.record_rollback(name="a", score=50.0)
        eng.record_rollback(name="b", score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_rollback(name="a", service="auth-svc", score=90.0)
        eng.record_rollback(name="b", service="api-gw", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="t1", analysis_score=20.0)
        eng.add_analysis(name="t2", analysis_score=20.0)
        eng.add_analysis(name="t3", analysis_score=80.0)
        eng.add_analysis(name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.record_rollback(
            name="test",
            rollback_type=RollbackType.DEPLOYMENT_ROLLBACK,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RollbackReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy range" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_rollback(name="test")
        eng.add_analysis(name="test")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rollback(
            name="test",
            rollback_type=RollbackType.CONFIG_RESTORE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "config_restore" in stats["type_distribution"]

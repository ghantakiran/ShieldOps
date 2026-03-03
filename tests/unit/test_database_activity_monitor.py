"""Tests for shieldops.security.database_activity_monitor — DatabaseActivityMonitor."""

from __future__ import annotations

from shieldops.security.database_activity_monitor import (
    ActivityRisk,
    DatabaseActivityAnalysis,
    DatabaseActivityMonitor,
    DatabaseActivityRecord,
    DatabaseActivityReport,
    DatabaseEngine,
    QueryType,
)


def _engine(**kw) -> DatabaseActivityMonitor:
    return DatabaseActivityMonitor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert QueryType.SELECT == "select"

    def test_e1_v2(self):
        assert QueryType.INSERT == "insert"

    def test_e1_v3(self):
        assert QueryType.UPDATE == "update"

    def test_e1_v4(self):
        assert QueryType.DELETE == "delete"

    def test_e1_v5(self):
        assert QueryType.DDL == "ddl"

    def test_e2_v1(self):
        assert ActivityRisk.EXFILTRATION == "exfiltration"

    def test_e2_v2(self):
        assert ActivityRisk.INJECTION == "injection"

    def test_e2_v3(self):
        assert ActivityRisk.PRIVILEGE_ABUSE == "privilege_abuse"

    def test_e2_v4(self):
        assert ActivityRisk.BULK_OPERATION == "bulk_operation"

    def test_e2_v5(self):
        assert ActivityRisk.NORMAL == "normal"

    def test_e3_v1(self):
        assert DatabaseEngine.POSTGRESQL == "postgresql"

    def test_e3_v2(self):
        assert DatabaseEngine.MYSQL == "mysql"

    def test_e3_v3(self):
        assert DatabaseEngine.MONGODB == "mongodb"

    def test_e3_v4(self):
        assert DatabaseEngine.REDIS == "redis"

    def test_e3_v5(self):
        assert DatabaseEngine.ELASTICSEARCH == "elasticsearch"


class TestModels:
    def test_rec(self):
        r = DatabaseActivityRecord()
        assert r.id and r.activity_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = DatabaseActivityAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DatabaseActivityReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_activity(
            activity_id="t",
            query_type=QueryType.INSERT,
            activity_risk=ActivityRisk.INJECTION,
            database_engine=DatabaseEngine.MYSQL,
            activity_score=92.0,
            service="s",
            team="t",
        )
        assert r.activity_id == "t" and r.activity_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_activity(activity_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_activity(activity_id="t")
        assert eng.get_activity(r.id) is not None

    def test_not_found(self):
        assert _engine().get_activity("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_activity(activity_id="a")
        eng.record_activity(activity_id="b")
        assert len(eng.list_activities()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_activity(activity_id="a", query_type=QueryType.SELECT)
        eng.record_activity(activity_id="b", query_type=QueryType.INSERT)
        assert len(eng.list_activities(query_type=QueryType.SELECT)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_activity(activity_id="a", activity_risk=ActivityRisk.EXFILTRATION)
        eng.record_activity(activity_id="b", activity_risk=ActivityRisk.INJECTION)
        assert len(eng.list_activities(activity_risk=ActivityRisk.EXFILTRATION)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_activity(activity_id="a", team="x")
        eng.record_activity(activity_id="b", team="y")
        assert len(eng.list_activities(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_activity(activity_id=f"t-{i}")
        assert len(eng.list_activities(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            activity_id="t", query_type=QueryType.INSERT, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(activity_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_activity(activity_id="a", query_type=QueryType.SELECT, activity_score=90.0)
        eng.record_activity(activity_id="b", query_type=QueryType.SELECT, activity_score=70.0)
        assert "select" in eng.analyze_query_distribution()

    def test_empty(self):
        assert _engine().analyze_query_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(activity_threshold=80.0)
        eng.record_activity(activity_id="a", activity_score=60.0)
        eng.record_activity(activity_id="b", activity_score=90.0)
        assert len(eng.identify_activity_gaps()) == 1

    def test_sorted(self):
        eng = _engine(activity_threshold=80.0)
        eng.record_activity(activity_id="a", activity_score=50.0)
        eng.record_activity(activity_id="b", activity_score=30.0)
        assert len(eng.identify_activity_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_activity(activity_id="a", service="s1", activity_score=80.0)
        eng.record_activity(activity_id="b", service="s2", activity_score=60.0)
        assert eng.rank_by_activity()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_activity() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(activity_id="t", analysis_score=float(v))
        assert eng.detect_activity_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(activity_id="t", analysis_score=float(v))
        assert eng.detect_activity_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_activity_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_activity(activity_id="t", activity_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_activity(activity_id="t")
        eng.add_analysis(activity_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_activity(activity_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_activity(activity_id="a")
        eng.record_activity(activity_id="b")
        eng.add_analysis(activity_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1

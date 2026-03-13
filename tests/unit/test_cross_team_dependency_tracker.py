"""Tests for CrossTeamDependencyTracker."""

from __future__ import annotations

from shieldops.topology.cross_team_dependency_tracker import (
    BlockingStatus,
    CrossTeamDependencyTracker,
    DependencyType,
    ImpactScope,
)


def _engine(**kw) -> CrossTeamDependencyTracker:
    return CrossTeamDependencyTracker(**kw)


class TestEnums:
    def test_dependency_type_values(self):
        for v in DependencyType:
            assert isinstance(v.value, str)

    def test_blocking_status_values(self):
        for v in BlockingStatus:
            assert isinstance(v.value, str)

    def test_impact_scope_values(self):
        for v in ImpactScope:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(source_team="t1")
        assert r.source_team == "t1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            source_team="t1",
            target_team="t2",
            impact_score=80.0,
        )
        assert r.impact_score == 80.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(source_team=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            source_team="t1",
            target_team="t2",
            impact_score=50.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "source_team")
        assert a.source_team == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(source_team="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(source_team="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(source_team="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapTeamDependencyGraph:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(source_team="t1", target_team="t2")
        eng.record_item(source_team="t1", target_team="t3")
        result = eng.map_team_dependency_graph()
        assert len(result) == 1
        assert result[0]["dependency_count"] == 2

    def test_empty(self):
        r = _engine().map_team_dependency_graph()
        assert r == []


class TestDetectBlockingDependencies:
    def test_with_blocked(self):
        eng = _engine()
        eng.record_item(
            source_team="t1",
            target_team="t2",
            status=BlockingStatus.BLOCKED,
            impact_score=90.0,
        )
        result = eng.detect_blocking_dependencies()
        assert len(result) == 1
        assert result[0]["status"] == "blocked"

    def test_empty(self):
        r = _engine().detect_blocking_dependencies()
        assert r == []


class TestRankDependenciesByDeliveryImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            source_team="t1",
            target_team="t2",
            impact_score=80.0,
        )
        eng.record_item(
            source_team="t1",
            target_team="t3",
            impact_score=40.0,
        )
        result = eng.rank_dependencies_by_delivery_impact()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_dependencies_by_delivery_impact()
        assert r == []

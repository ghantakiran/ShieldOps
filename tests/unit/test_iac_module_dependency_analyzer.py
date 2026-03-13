"""Tests for IacModuleDependencyAnalyzer."""

from __future__ import annotations

from shieldops.changes.iac_module_dependency_analyzer import (
    DependencyDepth,
    IacModuleDependencyAnalyzer,
    ModuleSource,
    UpdateRisk,
)


def _engine(**kw) -> IacModuleDependencyAnalyzer:
    return IacModuleDependencyAnalyzer(**kw)


class TestEnums:
    def test_module_source_values(self):
        for v in ModuleSource:
            assert isinstance(v.value, str)

    def test_dependency_depth_values(self):
        for v in DependencyDepth:
            assert isinstance(v.value, str)

    def test_update_risk_values(self):
        for v in UpdateRisk:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(module_id="m1")
        assert r.module_id == "m1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(module_id=f"m-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            module_id="m1",
            dependent_count=5,
            dependency_count=3,
        )
        a = eng.process(r.id)
        assert hasattr(a, "module_id")
        assert a.impact_score == 65.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_circular(self):
        eng = _engine()
        r = eng.record_item(
            module_id="m1",
            dependency_depth=DependencyDepth.CIRCULAR,
        )
        a = eng.process(r.id)
        assert a.has_circular is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(module_id="m1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(module_id="m1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(module_id="m1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapModuleDependencyGraph:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            module_id="m1",
            dependent_count=3,
            dependency_count=2,
        )
        result = eng.map_module_dependency_graph()
        assert len(result) == 1
        assert result[0]["total_dependents"] == 3

    def test_empty(self):
        r = _engine().map_module_dependency_graph()
        assert r == []


class TestDetectCircularDependencies:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            module_id="m1",
            dependency_depth=DependencyDepth.CIRCULAR,
        )
        result = eng.detect_circular_dependencies()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().detect_circular_dependencies()
        assert r == []


class TestRankModulesByUpdateImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            module_id="m1",
            dependent_count=5,
        )
        eng.record_item(
            module_id="m2",
            dependent_count=10,
        )
        result = eng.rank_modules_by_update_impact()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_modules_by_update_impact()
        assert r == []

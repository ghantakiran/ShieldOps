"""Tests for CrossFrameworkControlMapper."""

from __future__ import annotations

from shieldops.compliance.cross_framework_control_mapper import (
    ControlDomain,
    CrossFrameworkControlMapper,
    Framework,
    MappingConfidence,
)


def _engine(**kw) -> CrossFrameworkControlMapper:
    return CrossFrameworkControlMapper(**kw)


class TestEnums:
    def test_framework_values(self):
        for v in Framework:
            assert isinstance(v.value, str)

    def test_mapping_confidence_values(self):
        for v in MappingConfidence:
            assert isinstance(v.value, str)

    def test_control_domain_values(self):
        for v in ControlDomain:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(control_id="c1")
        assert r.control_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(control_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(control_id="c1", coverage_score=75.0)
        a = eng.process(r.id)
        assert hasattr(a, "control_id")
        assert a.control_id == "c1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(control_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeControlOverlapMatrix:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            control_id="c1",
            framework=Framework.SOC2,
            mapped_to_framework="iso27001",
        )
        result = eng.compute_control_overlap_matrix()
        assert len(result) == 1
        assert result[0]["source_framework"] == "soc2"

    def test_empty(self):
        assert _engine().compute_control_overlap_matrix() == []


class TestDetectUnmappedControls:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(control_id="c1", coverage_score=0.0)
        result = eng.detect_unmapped_controls()
        assert len(result) == 1
        assert result[0]["control_id"] == "c1"

    def test_empty(self):
        assert _engine().detect_unmapped_controls() == []


class TestRankFrameworksByCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(control_id="c1", framework=Framework.SOC2, coverage_score=80.0)
        eng.add_record(control_id="c2", framework=Framework.NIST, coverage_score=60.0)
        result = eng.rank_frameworks_by_coverage()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_frameworks_by_coverage() == []

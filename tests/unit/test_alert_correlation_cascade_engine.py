"""Tests for AlertCorrelationCascadeEngine."""

from __future__ import annotations

from shieldops.observability.alert_correlation_cascade_engine import (
    AlertCorrelationCascadeEngine,
    CascadeDepth,
    CascadeRole,
    CorrelationMethod,
)


def _engine(**kw) -> AlertCorrelationCascadeEngine:
    return AlertCorrelationCascadeEngine(**kw)


class TestEnums:
    def test_cascade_role_values(self):
        for v in CascadeRole:
            assert isinstance(v.value, str)

    def test_correlation_method_values(self):
        for v in CorrelationMethod:
            assert isinstance(v.value, str)

    def test_cascade_depth_values(self):
        for v in CascadeDepth:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1")
        assert r.alert_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_id=f"a-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            alert_id="a1",
            cascade_id="c1",
            cascade_role=CascadeRole.ROOT_CAUSE,
        )
        assert r.cascade_id == "c1"


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            alert_id="a1",
            cascade_id="c1",
            cascade_role=CascadeRole.ROOT_CAUSE,
        )
        a = eng.process(r.id)
        assert hasattr(a, "alert_id")
        assert a.alert_id == "a1"
        assert a.is_root_cause is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
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
        eng.add_record(alert_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestBuildCascadeTree:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(alert_id="a1", cascade_id="c1")
        eng.add_record(alert_id="a2", cascade_id="c1")
        result = eng.build_cascade_tree()
        assert len(result) == 1
        assert result[0]["member_count"] == 2

    def test_empty(self):
        assert _engine().build_cascade_tree() == []


class TestIdentifyRootCauseAlerts:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            cascade_role=CascadeRole.ROOT_CAUSE,
            cascade_id="c1",
            impact_score=90.0,
        )
        result = eng.identify_root_cause_alerts()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().identify_root_cause_alerts()
        assert r == []


class TestQuantifyCascadeBlastRadius:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            cascade_id="c1",
            impact_score=50.0,
        )
        eng.add_record(
            alert_id="a2",
            cascade_id="c1",
            impact_score=30.0,
        )
        result = eng.quantify_cascade_blast_radius()
        assert len(result) == 1
        assert result[0]["blast_radius"] == 2

    def test_empty(self):
        r = _engine().quantify_cascade_blast_radius()
        assert r == []

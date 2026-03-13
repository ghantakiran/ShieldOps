"""Tests for CompliancePostureDriftEngine."""

from __future__ import annotations

from shieldops.compliance.compliance_posture_drift_engine import (
    CompliancePostureDriftEngine,
    DriftDirection,
    DriftSeverity,
    PostureDomain,
)


def _engine(**kw) -> CompliancePostureDriftEngine:
    return CompliancePostureDriftEngine(**kw)


class TestEnums:
    def test_drift_direction_values(self):
        for v in DriftDirection:
            assert isinstance(v.value, str)

    def test_drift_severity_values(self):
        for v in DriftSeverity:
            assert isinstance(v.value, str)

    def test_posture_domain_values(self):
        for v in PostureDomain:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(domain_id="d1")
        assert r.domain_id == "d1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(domain_id=f"d-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(domain_id="d1", drift_score=25.0)
        a = eng.process(r.id)
        assert hasattr(a, "domain_id")
        assert a.domain_id == "d1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(domain_id="d1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(domain_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(domain_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputePostureDriftScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(domain_id="d1", drift_score=15.0)
        result = eng.compute_posture_drift_score()
        assert len(result) == 1
        assert result[0]["domain_id"] == "d1"

    def test_empty(self):
        assert _engine().compute_posture_drift_score() == []


class TestDetectDriftAcceleration:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(domain_id="d1", drift_score=10.0)
        eng.add_record(domain_id="d1", drift_score=20.0)
        result = eng.detect_drift_acceleration()
        assert len(result) == 1
        assert result[0]["acceleration"] == 10.0

    def test_empty(self):
        assert _engine().detect_drift_acceleration() == []


class TestRankDomainsByDriftSeverity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(domain_id="d1", drift_score=50.0)
        eng.add_record(domain_id="d2", drift_score=80.0)
        result = eng.rank_domains_by_drift_severity()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_domains_by_drift_severity() == []

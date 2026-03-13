"""Tests for OrganizationalResilienceScorer."""

from __future__ import annotations

from shieldops.analytics.organizational_resilience_scorer import (
    GapType,
    MaturityLevel,
    OrganizationalResilienceScorer,
    ResilienceDimension,
)


def _engine(**kw) -> OrganizationalResilienceScorer:
    return OrganizationalResilienceScorer(**kw)


class TestEnums:
    def test_resilience_dimension_values(self):
        for v in ResilienceDimension:
            assert isinstance(v.value, str)

    def test_gap_type_values(self):
        for v in GapType:
            assert isinstance(v.value, str)

    def test_maturity_level_values(self):
        for v in MaturityLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(capability_id="c1")
        assert r.capability_id == "c1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            capability_id="c1",
            resilience_score=80.0,
            recovery_time_hours=2.0,
        )
        assert r.resilience_score == 80.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(capability_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            capability_id="c1",
            resilience_score=70.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "capability_id")
        assert a.capability_id == "c1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(capability_id="c1")
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
        eng.add_record(capability_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(capability_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeResilienceScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            capability_id="c1",
            resilience_score=85.0,
        )
        result = eng.compute_resilience_score()
        assert len(result) == 1
        assert result[0]["resilience_score"] == 85.0

    def test_empty(self):
        r = _engine().compute_resilience_score()
        assert r == []


class TestDetectResilienceGaps:
    def test_with_gaps(self):
        eng = _engine()
        eng.add_record(
            capability_id="c1",
            maturity=MaturityLevel.INITIAL,
            resilience_score=20.0,
        )
        result = eng.detect_resilience_gaps()
        assert len(result) == 1
        assert result[0]["maturity"] == "initial"

    def test_empty(self):
        r = _engine().detect_resilience_gaps()
        assert r == []


class TestRankCapabilitiesByImprovementPriority:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            capability_id="c1",
            resilience_score=40.0,
            recovery_time_hours=10.0,
        )
        eng.add_record(
            capability_id="c2",
            resilience_score=80.0,
            recovery_time_hours=1.0,
        )
        result = eng.rank_capabilities_by_improvement_priority()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_capabilities_by_improvement_priority()
        assert r == []

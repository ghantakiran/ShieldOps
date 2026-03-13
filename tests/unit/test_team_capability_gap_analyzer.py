"""Tests for TeamCapabilityGapAnalyzer."""

from __future__ import annotations

from shieldops.analytics.team_capability_gap_analyzer import (
    CapabilityDomain,
    GapSeverity,
    RemediationPath,
    TeamCapabilityGapAnalyzer,
)


def _engine(**kw) -> TeamCapabilityGapAnalyzer:
    return TeamCapabilityGapAnalyzer(**kw)


class TestEnums:
    def test_capability_domain_values(self):
        for v in CapabilityDomain:
            assert isinstance(v.value, str)

    def test_gap_severity_values(self):
        for v in GapSeverity:
            assert isinstance(v.value, str)

    def test_remediation_path_values(self):
        for v in RemediationPath:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(gap_id="g1")
        assert r.gap_id == "g1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            gap_id="g1",
            team_id="t1",
            impact_score=90.0,
            current_level=3.0,
            required_level=8.0,
        )
        assert r.impact_score == 90.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(gap_id=f"g-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            gap_id="g1",
            current_level=3.0,
            required_level=8.0,
            impact_score=90.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "gap_id")
        assert a.gap_size == 5.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(gap_id="g1")
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
        eng.add_record(gap_id="g1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(gap_id="g1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestIdentifyCapabilityGaps:
    def test_with_gaps(self):
        eng = _engine()
        eng.add_record(
            gap_id="g1",
            team_id="t1",
            current_level=2.0,
            required_level=8.0,
        )
        result = eng.identify_capability_gaps()
        assert len(result) == 1
        assert result[0]["gap_count"] == 1

    def test_empty(self):
        r = _engine().identify_capability_gaps()
        assert r == []


class TestComputeGapCriticality:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            gap_id="g1",
            current_level=2.0,
            required_level=8.0,
            impact_score=90.0,
        )
        result = eng.compute_gap_criticality()
        assert len(result) == 1
        assert result[0]["criticality"] == 540.0

    def test_empty(self):
        r = _engine().compute_gap_criticality()
        assert r == []


class TestRankGapsByBusinessImpact:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            gap_id="g1",
            team_id="t1",
            impact_score=90.0,
        )
        eng.add_record(
            gap_id="g2",
            team_id="t1",
            impact_score=40.0,
        )
        result = eng.rank_gaps_by_business_impact()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_gaps_by_business_impact()
        assert r == []

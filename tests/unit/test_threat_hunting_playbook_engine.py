"""Tests for ThreatHuntingPlaybookEngine."""

from __future__ import annotations

from shieldops.security.threat_hunting_playbook_engine import (
    HuntOutcome,
    HuntType,
    PlaybookMaturity,
    ThreatHuntingPlaybookEngine,
)


def _engine(**kw) -> ThreatHuntingPlaybookEngine:
    return ThreatHuntingPlaybookEngine(**kw)


class TestEnums:
    def test_type_hypothesis(self):
        assert HuntType.HYPOTHESIS_DRIVEN == "hypothesis_driven"

    def test_type_indicator(self):
        assert HuntType.INDICATOR_BASED == "indicator_based"

    def test_type_behavioral(self):
        assert HuntType.BEHAVIORAL == "behavioral"

    def test_type_automated(self):
        assert HuntType.AUTOMATED == "automated"

    def test_maturity_draft(self):
        assert PlaybookMaturity.DRAFT == "draft"

    def test_maturity_tested(self):
        assert PlaybookMaturity.TESTED == "tested"

    def test_maturity_validated(self):
        assert PlaybookMaturity.VALIDATED == "validated"

    def test_maturity_production(self):
        assert PlaybookMaturity.PRODUCTION == "production"

    def test_outcome_confirmed(self):
        assert HuntOutcome.CONFIRMED == "confirmed"

    def test_outcome_suspicious(self):
        assert HuntOutcome.SUSPICIOUS == "suspicious"

    def test_outcome_benign(self):
        assert HuntOutcome.BENIGN == "benign"

    def test_outcome_inconclusive(self):
        assert HuntOutcome.INCONCLUSIVE == "inconclusive"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            hunt_id="h1",
            hunt_type=HuntType.BEHAVIORAL,
            effectiveness_score=85.0,
        )
        assert r.hunt_id == "h1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(hunt_id=f"h-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            hunt_id="h1",
            effectiveness_score=80.0,
            coverage_pct=90.0,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.hunt_id == "h1"
        assert a.analysis_score > 0

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(hunt_id="h1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(hunt_id="h1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(hunt_id="h1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestGenerateHuntHypothesis:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            hunt_id="h1",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            effectiveness_score=90.0,
        )
        result = eng.generate_hunt_hypothesis()
        assert len(result) == 1
        assert result[0]["hunt_type"] == "hypothesis_driven"

    def test_empty(self):
        assert _engine().generate_hunt_hypothesis() == []


class TestEvaluatePlaybookCoverage:
    def test_basic(self):
        eng = _engine()
        eng.add_record(hunt_id="h1", coverage_pct=85.0)
        result = eng.evaluate_playbook_coverage()
        assert result["overall_coverage"] == 85.0

    def test_empty(self):
        result = _engine().evaluate_playbook_coverage()
        assert result["overall_coverage"] == 0.0


class TestScoreHuntEffectiveness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            hunt_id="h1",
            outcome=HuntOutcome.CONFIRMED,
            effectiveness_score=92.0,
        )
        result = eng.score_hunt_effectiveness()
        assert result["overall_effectiveness"] == 92.0

    def test_empty(self):
        result = _engine().score_hunt_effectiveness()
        assert result["overall_effectiveness"] == 0.0

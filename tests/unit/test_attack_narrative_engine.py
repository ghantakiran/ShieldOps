"""Tests for AttackNarrativeEngine."""

from __future__ import annotations

from shieldops.security.attack_narrative_engine import (
    AttackNarrativeEngine,
    EvidenceStrength,
    NarrativePhase,
    StoryCompleteness,
)


def _engine(**kw) -> AttackNarrativeEngine:
    return AttackNarrativeEngine(**kw)


class TestEnums:
    def test_phase_access(self):
        assert NarrativePhase.INITIAL_ACCESS == "initial_access"

    def test_phase_execution(self):
        assert NarrativePhase.EXECUTION == "execution"

    def test_phase_persistence(self):
        assert NarrativePhase.PERSISTENCE == "persistence"

    def test_phase_exfiltration(self):
        assert NarrativePhase.EXFILTRATION == "exfiltration"

    def test_ev_conclusive(self):
        assert EvidenceStrength.CONCLUSIVE == "conclusive"

    def test_ev_strong(self):
        assert EvidenceStrength.STRONG == "strong"

    def test_ev_moderate(self):
        assert EvidenceStrength.MODERATE == "moderate"

    def test_ev_circumstantial(self):
        assert EvidenceStrength.CIRCUMSTANTIAL == "circumstantial"

    def test_comp_complete(self):
        assert StoryCompleteness.COMPLETE == "complete"

    def test_comp_partial(self):
        assert StoryCompleteness.PARTIAL == "partial"

    def test_comp_fragment(self):
        assert StoryCompleteness.FRAGMENTARY == "fragmentary"

    def test_comp_unknown(self):
        assert StoryCompleteness.UNKNOWN == "unknown"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            narrative_id="n1",
            phase=NarrativePhase.EXECUTION,
            confidence_score=0.9,
        )
        assert r.narrative_id == "n1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(narrative_id=f"n-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            narrative_id="n1",
            confidence_score=0.8,
            evidence=EvidenceStrength.STRONG,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.narrative_id == "n1"

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(narrative_id="n1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(narrative_id="n1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(narrative_id="n1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestConstructAttackStory:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            narrative_id="n1",
            phase=NarrativePhase.INITIAL_ACCESS,
            confidence_score=0.9,
        )
        result = eng.construct_attack_story()
        assert len(result) == 1
        assert result[0]["phase"] == "initial_access"

    def test_empty(self):
        assert _engine().construct_attack_story() == []


class TestIdentifyNarrativeGaps:
    def test_basic(self):
        eng = _engine(confidence_threshold=0.8)
        eng.add_record(
            narrative_id="n1",
            confidence_score=0.3,
            completeness=StoryCompleteness.FRAGMENTARY,
        )
        result = eng.identify_narrative_gaps()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().identify_narrative_gaps() == []


class TestScoreStoryConfidence:
    def test_basic(self):
        eng = _engine()
        eng.add_record(narrative_id="n1", confidence_score=0.85)
        result = eng.score_story_confidence()
        assert result["overall_confidence"] == 0.85

    def test_empty(self):
        result = _engine().score_story_confidence()
        assert result["overall_confidence"] == 0.0

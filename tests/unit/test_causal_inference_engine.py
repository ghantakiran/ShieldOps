"""Tests for CausalInferenceEngine."""

from __future__ import annotations

from shieldops.analytics.causal_inference_engine import (
    CausalInferenceEngine,
    CausalRelation,
    EvidenceStrength,
    InterventionType,
)


def _engine(**kw) -> CausalInferenceEngine:
    return CausalInferenceEngine(**kw)


class TestEnums:
    def test_causal_relation(self):
        assert CausalRelation.CAUSES == "causes"

    def test_evidence_strength(self):
        assert EvidenceStrength.STRONG == "strong"

    def test_intervention_type(self):
        assert InterventionType.DEPLOYMENT == "deployment"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(
            source_event="deploy",
            target_event="cpu_spike",
        )
        assert rec.source_event == "deploy"
        assert rec.target_event == "cpu_spike"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                source_event=f"e-{i}",
                target_event="target",
            )
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(
            source_event="deploy",
            target_event="spike",
        )
        result = eng.process("deploy")
        assert isinstance(result, dict)
        assert result["source_event"] == "deploy"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestEvaluateCausality:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            source_event="deploy",
            target_event="spike",
            relation=CausalRelation.CAUSES,
        )
        result = eng.evaluate_causality("deploy", "spike")
        assert isinstance(result, dict)


class TestBuildCounterfactual:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            source_event="deploy",
            target_event="spike",
        )
        result = eng.build_counterfactual("deploy")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(
            source_event="deploy",
            target_event="spike",
        )
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            source_event="deploy",
            target_event="spike",
        )
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(
            source_event="deploy",
            target_event="spike",
        )
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0

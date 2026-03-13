"""Tests for AgentKnowledgeDistiller."""

from __future__ import annotations

from shieldops.knowledge.agent_knowledge_distiller import (
    AgentKnowledgeDistiller,
    DistillationMethod,
    KnowledgeType,
    RetentionPriority,
)


def _engine(**kw) -> AgentKnowledgeDistiller:
    return AgentKnowledgeDistiller(**kw)


class TestEnums:
    def test_knowledge_type_values(self):
        assert isinstance(KnowledgeType.PROCEDURAL, str)
        assert isinstance(KnowledgeType.DECLARATIVE, str)
        assert isinstance(KnowledgeType.HEURISTIC, str)
        assert isinstance(KnowledgeType.CONTEXTUAL, str)

    def test_distillation_method_values(self):
        assert isinstance(DistillationMethod.SUMMARIZATION, str)
        assert isinstance(DistillationMethod.COMPRESSION, str)
        assert isinstance(DistillationMethod.EXTRACTION, str)
        assert isinstance(DistillationMethod.SYNTHESIS, str)

    def test_retention_priority_values(self):
        assert isinstance(RetentionPriority.CRITICAL, str)
        assert isinstance(RetentionPriority.HIGH, str)
        assert isinstance(RetentionPriority.MEDIUM, str)
        assert isinstance(RetentionPriority.LOW, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            topic="k8s-restart",
            knowledge_type=KnowledgeType.PROCEDURAL,
            density_score=0.8,
        )
        assert r.topic == "k8s-restart"
        assert r.density_score == 0.8

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(topic=f"topic-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(topic="topic-001")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(topic="topic-001")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        assert "total_records" in eng.get_stats()

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(topic="t1")
        eng.add_record(topic="t2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(topic="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestDistillAgentLearnings:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(agent_id="a1", topic="t1", density_score=0.8)
        result = eng.distill_agent_learnings("a1")
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.distill_agent_learnings("a1") == []


class TestComputeKnowledgeDensity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(agent_id="a1", density_score=0.8)
        result = eng.compute_knowledge_density("a1")
        assert result["avg_density"] == 0.8

    def test_empty(self):
        eng = _engine()
        result = eng.compute_knowledge_density("a1")
        assert result["status"] == "no_data"


class TestIdentifyKnowledgeGaps:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(agent_id="a1", topic="t1", density_score=0.1)
        eng.add_record(agent_id="a1", topic="t2", density_score=0.9)
        result = eng.identify_knowledge_gaps("a1")
        assert len(result) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_knowledge_gaps("a1") == []

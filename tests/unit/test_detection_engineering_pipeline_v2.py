"""Tests for DetectionEngineeringPipelineV2."""

from __future__ import annotations

from shieldops.security.detection_engineering_pipeline_v2 import (
    DeploymentStatus,
    DetectionEngineeringPipelineV2,
    RuleEffectiveness,
    RuleLifecycleStage,
    RuleRecord,
)


def _engine(**kw) -> DetectionEngineeringPipelineV2:
    return DetectionEngineeringPipelineV2(**kw)


class TestEnums:
    def test_lifecycle_draft(self):
        assert RuleLifecycleStage.DRAFT == "draft"

    def test_effectiveness(self):
        assert RuleEffectiveness.HIGH == "high"

    def test_deployment(self):
        assert DeploymentStatus.DEPLOYED == "deployed"


class TestModels:
    def test_record_defaults(self):
        r = RuleRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(rule_name="detect-ssh-brute", lifecycle_stage=RuleLifecycleStage.DRAFT)
        assert rec.rule_name == "detect-ssh-brute"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(rule_name=f"rule-{i}")
        assert len(eng._records) == 3


class TestEffectivenessMetrics:
    def test_basic(self):
        eng = _engine()
        eng.add_record(rule_name="r1", lifecycle_stage=RuleLifecycleStage.PRODUCTION)
        result = eng.compute_effectiveness_metrics()
        assert isinstance(result, dict)


class TestGaps:
    def test_basic(self):
        eng = _engine()
        eng.add_record(rule_name="r1")
        result = eng.identify_gaps()
        assert isinstance(result, list)


class TestDeploymentReadiness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(rule_name="r1", lifecycle_stage=RuleLifecycleStage.STAGING)
        result = eng.compute_deployment_readiness()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(rule_name="r1", service="api")
        result = eng.process("r1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(rule_name="r1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(rule_name="r1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(rule_name="r1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0

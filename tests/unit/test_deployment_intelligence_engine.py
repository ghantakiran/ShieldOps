"""Tests for shieldops.changes.deployment_intelligence_engine — DeploymentIntelligenceEngine."""

from __future__ import annotations

from shieldops.changes.deployment_intelligence_engine import (
    DeploymentIntelligenceEngine,
    DeploymentOutcome,
    DeploymentStrategy,
    RollbackRisk,
)


def _engine(**kw) -> DeploymentIntelligenceEngine:
    return DeploymentIntelligenceEngine(**kw)


class TestEnums:
    def test_outcome_success(self):
        assert DeploymentOutcome.SUCCESS == "success"

    def test_strategy_canary(self):
        assert DeploymentStrategy.CANARY == "canary"

    def test_rollback_risk(self):
        assert RollbackRisk.HIGH == "high"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="v2.1.0-deploy", outcome=DeploymentOutcome.SUCCESS)
        assert rec.name == "v2.1.0-deploy"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"deploy-{i}")
        assert len(eng._records) == 3


class TestRollbackRiskPrediction:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", outcome=DeploymentOutcome.ROLLED_BACK)
        eng.record_item(name="d2", outcome=DeploymentOutcome.SUCCESS)
        result = eng.predict_rollback_risk()
        assert isinstance(result, list)


class TestSuccessPatterns:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", outcome=DeploymentOutcome.SUCCESS)
        result = eng.analyze_success_patterns()
        assert isinstance(result, dict)


class TestRiskyServices:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1", outcome=DeploymentOutcome.FAILED, service="api")
        result = eng.identify_risky_services()
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="d1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="d1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="d1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0

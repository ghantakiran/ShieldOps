"""Tests for DeveloperOnboardingEngine."""

from __future__ import annotations

from shieldops.knowledge.developer_onboarding_engine import (
    BottleneckType,
    DeveloperOnboardingEngine,
    OnboardingOutcome,
    OnboardingPhase,
)


def _engine(**kw) -> DeveloperOnboardingEngine:
    return DeveloperOnboardingEngine(**kw)


class TestEnums:
    def test_onboarding_phase_values(self):
        assert OnboardingPhase.orientation == "orientation"
        assert OnboardingPhase.environment_setup == "environment_setup"
        assert OnboardingPhase.first_commit == "first_commit"
        assert OnboardingPhase.first_deploy == "first_deploy"
        assert OnboardingPhase.fully_productive == "fully_productive"

    def test_bottleneck_type_values(self):
        assert BottleneckType.tooling == "tooling"
        assert BottleneckType.documentation == "documentation"
        assert BottleneckType.access == "access"
        assert BottleneckType.mentorship == "mentorship"
        assert BottleneckType.complexity == "complexity"

    def test_onboarding_outcome_values(self):
        assert OnboardingOutcome.completed == "completed"
        assert OnboardingOutcome.in_progress == "in_progress"
        assert OnboardingOutcome.stalled == "stalled"
        assert OnboardingOutcome.abandoned == "abandoned"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            developer_id="dev-1",
            team="platform",
            phase=OnboardingPhase.first_commit,
        )
        assert r.developer_id == "dev-1"
        assert r.phase == OnboardingPhase.first_commit

    def test_eviction_at_max(self):
        eng = _engine(max_records=20)
        for i in range(25):
            eng.add_record(developer_id=f"d-{i}")
        stats = eng.get_stats()
        assert stats["total_records"] < 25


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(developer_id="dev-1")
        result = eng.process(r.id)
        assert isinstance(result.productivity_score, float)

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result.record_id == ""


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        r = eng.add_record(developer_id="d")
        eng.process(r.id)
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(developer_id="x")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.add_record(developer_id="x")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestComputeTimeToProductivity:
    def test_returns_dict(self):
        eng = _engine()
        eng.add_record(
            developer_id="d",
            team="t",
            outcome=OnboardingOutcome.completed,
            days_elapsed=20,
        )
        result = eng.compute_time_to_productivity()
        assert isinstance(result, dict)


class TestIdentifyBottlenecks:
    def test_returns_dict(self):
        eng = _engine()
        eng.add_record(
            developer_id="d",
            outcome=OnboardingOutcome.stalled,
            bottleneck_type=BottleneckType.tooling,
        )
        result = eng.identify_bottlenecks()
        assert isinstance(result, dict)


class TestRecommendKnowledgePaths:
    def test_returns_list(self):
        eng = _engine()
        eng.add_record(developer_id="d1")
        result = eng.recommend_knowledge_paths("d1")
        assert isinstance(result, list)

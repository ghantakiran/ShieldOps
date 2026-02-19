"""End-to-end integration tests for the Learning Agent.

Tests the full LangGraph workflow: gather_data → analyze_patterns →
recommend_playbooks → adjust_thresholds → synthesize, with mocked LLM.
"""

from unittest.mock import AsyncMock, patch

import pytest

from shieldops.agents.learning.models import LearningState
from shieldops.agents.learning.prompts import (
    ImprovementSynthesisResult,
    PatternAnalysisResult,
    PlaybookRecommendationResult,
    ThresholdRecommendationResult,
)
from shieldops.agents.learning.runner import LearningRunner


@pytest.fixture
def mock_incident_store():
    """Fake incident store with test outcome data."""
    store = AsyncMock()
    store.query.return_value = {
        "period": "30d",
        "total_incidents": 5,
        "outcomes": [
            {
                "incident_id": "inc-001",
                "alert_type": "high_cpu",
                "environment": "production",
                "root_cause": "Memory leak in API service",
                "resolution_action": "restart_pod",
                "investigation_duration_ms": 45000,
                "remediation_duration_ms": 12000,
                "was_automated": True,
                "was_correct": True,
                "feedback": "",
            },
            {
                "incident_id": "inc-002",
                "alert_type": "high_cpu",
                "environment": "production",
                "root_cause": "Memory leak in API service",
                "resolution_action": "restart_pod",
                "investigation_duration_ms": 38000,
                "remediation_duration_ms": 11000,
                "was_automated": True,
                "was_correct": True,
                "feedback": "Same recurring issue",
            },
            {
                "incident_id": "inc-003",
                "alert_type": "latency_spike",
                "environment": "production",
                "root_cause": "Database connection pool exhaustion",
                "resolution_action": "scale_horizontal",
                "investigation_duration_ms": 120000,
                "remediation_duration_ms": 30000,
                "was_automated": False,
                "was_correct": True,
                "feedback": "Should auto-scale connections",
            },
            {
                "incident_id": "inc-004",
                "alert_type": "oom_kill",
                "environment": "staging",
                "root_cause": "Memory limit too low",
                "resolution_action": "increase_resources",
                "investigation_duration_ms": 25000,
                "remediation_duration_ms": 8000,
                "was_automated": True,
                "was_correct": True,
                "feedback": "",
            },
            {
                "incident_id": "inc-005",
                "alert_type": "high_cpu",
                "environment": "production",
                "root_cause": "Runaway cron job",
                "resolution_action": "restart_pod",
                "investigation_duration_ms": 60000,
                "remediation_duration_ms": 15000,
                "was_automated": True,
                "was_correct": False,
                "feedback": "Restart didn't fix it — needed to kill the cron",
            },
        ],
    }
    return store


@pytest.fixture
def mock_playbook_store():
    """Fake playbook store with test playbooks."""
    store = AsyncMock()
    store.list.return_value = {
        "playbooks": [
            {
                "playbook_id": "pb-001",
                "alert_type": "high_cpu",
                "title": "High CPU Remediation",
                "description": "Steps for CPU spikes",
                "version": "1.0",
            },
            {
                "playbook_id": "pb-002",
                "alert_type": "oom_kill",
                "title": "OOM Kill Response",
                "description": "Steps for OOM events",
                "version": "1.0",
            },
        ],
        "total": 2,
    }
    return store


@pytest.fixture
def learning_llm_responses():
    """Deterministic LLM responses for learning agent tests."""
    return {
        PatternAnalysisResult: PatternAnalysisResult(
            summary="Recurring memory leak pattern and CPU-related incidents",
            recurring_patterns=[
                "Memory leak in API service causing repeated high_cpu alerts",
                "Restart doesn't always fix root cause (e.g. runaway cron)",
            ],
            common_root_causes=["Memory leaks", "Runaway processes", "Connection pool exhaustion"],
            automation_gaps=["Connection pool scaling not automated"],
        ),
        PlaybookRecommendationResult: PlaybookRecommendationResult(
            summary="Update CPU playbook to check for cron jobs; add connection pool playbook",
            new_playbooks=["latency_spike: Auto-scale database connections"],
            playbook_improvements=[
                "high_cpu: Add step to check for runaway cron jobs before restarting"
            ],
            deprecated_steps=["high_cpu: Remove blind restart as first action"],
        ),
        ThresholdRecommendationResult: ThresholdRecommendationResult(
            summary="Reduce CPU threshold noise by increasing duration",
            adjustments=[
                "cpu_usage_percent warning: 80%/5m -> 85%/8m (reduce noise from transient spikes)"
            ],
            estimated_noise_reduction=20.0,
        ),
        ImprovementSynthesisResult: ImprovementSynthesisResult(
            improvement_score=72.0,
            summary="Good automation rate but recurring patterns need permanent fixes",
            key_improvements=[
                "Fix memory leak permanently",
                "Add cron job detection to CPU playbook",
                "Automate connection pool scaling",
            ],
            risks=["Continued alert fatigue from recurring memory leaks"],
        ),
    }


@pytest.mark.asyncio
async def test_learning_full_pipeline(
    mock_incident_store,
    mock_playbook_store,
    learning_llm_responses,
):
    """Learning runner completes full cycle with patterns, playbooks, thresholds."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return learning_llm_responses[schema]

    with patch("shieldops.agents.learning.nodes.llm_structured", side_effect=fake_llm):
        runner = LearningRunner(
            incident_store=mock_incident_store,
            playbook_store=mock_playbook_store,
        )

        result = await runner.learn(learning_type="full", period="30d")

    assert isinstance(result, LearningState)
    assert result.error is None
    assert result.total_incidents_analyzed > 0
    assert len(result.pattern_insights) > 0
    assert len(result.playbook_updates) > 0
    assert len(result.threshold_adjustments) > 0
    assert result.improvement_score > 0
    assert len(result.reasoning_chain) >= 3


@pytest.mark.asyncio
async def test_learning_stores_cycle(
    mock_incident_store,
    mock_playbook_store,
    learning_llm_responses,
):
    """Learning runner stores completed cycle in its internal dict."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return learning_llm_responses[schema]

    with patch("shieldops.agents.learning.nodes.llm_structured", side_effect=fake_llm):
        runner = LearningRunner(
            incident_store=mock_incident_store,
            playbook_store=mock_playbook_store,
        )
        result = await runner.learn()

    listed = runner.list_cycles()
    assert len(listed) == 1
    assert listed[0]["learning_id"] == result.learning_id


@pytest.mark.asyncio
async def test_learning_handles_llm_failure(
    mock_incident_store,
    mock_playbook_store,
):
    """Learning degrades gracefully when LLM calls fail."""
    with patch(
        "shieldops.agents.learning.nodes.llm_structured",
        side_effect=RuntimeError("LLM provider unavailable"),
    ):
        runner = LearningRunner(
            incident_store=mock_incident_store,
            playbook_store=mock_playbook_store,
        )
        result = await runner.learn()

    assert isinstance(result, LearningState)
    # Nodes catch LLM errors, so the run should still complete
    assert len(result.reasoning_chain) >= 1


@pytest.mark.asyncio
async def test_learning_with_no_stores():
    """Learning works with no stores configured (uses stub data)."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == PatternAnalysisResult:
            return PatternAnalysisResult(
                summary="Stub data analysis",
                recurring_patterns=["Memory leaks"],
                common_root_causes=["Memory leaks"],
                automation_gaps=[],
            )
        if schema == PlaybookRecommendationResult:
            return PlaybookRecommendationResult(
                summary="No updates",
                new_playbooks=[],
                playbook_improvements=[],
                deprecated_steps=[],
            )
        if schema == ThresholdRecommendationResult:
            return ThresholdRecommendationResult(
                summary="No changes",
                adjustments=[],
                estimated_noise_reduction=0.0,
            )
        return ImprovementSynthesisResult(
            improvement_score=50.0,
            summary="Baseline",
            key_improvements=[],
            risks=[],
        )

    with patch("shieldops.agents.learning.nodes.llm_structured", side_effect=fake_llm):
        runner = LearningRunner()
        result = await runner.learn()

    assert isinstance(result, LearningState)
    assert result.error is None


@pytest.mark.asyncio
async def test_learning_records_reasoning_chain(
    mock_incident_store,
    mock_playbook_store,
    learning_llm_responses,
):
    """Each learning stage records a reasoning step."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return learning_llm_responses[schema]

    with patch("shieldops.agents.learning.nodes.llm_structured", side_effect=fake_llm):
        runner = LearningRunner(
            incident_store=mock_incident_store,
            playbook_store=mock_playbook_store,
        )
        result = await runner.learn()

    step_names = [step.action for step in result.reasoning_chain]
    assert len(step_names) >= 2
    # Verify key steps occurred
    assert any("gather" in s or "collect" in s or "data" in s for s in step_names)

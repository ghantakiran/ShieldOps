"""Tests for learning agent production store — repository methods, adapters, and wiring."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.agents.learning.runner import LearningRunner
from shieldops.agents.learning.tools import (
    IncidentStoreAdapter,
    LearningToolkit,
    PlaybookStoreAdapter,
)
from shieldops.playbooks.loader import Playbook, PlaybookLoader, PlaybookTrigger

# ── IncidentStoreAdapter ────────────────────────────────────────


class TestIncidentStoreAdapter:
    @pytest.mark.asyncio
    async def test_query_delegates_to_repository(self):
        repo = AsyncMock()
        repo.query_incident_outcomes.return_value = {
            "period": "7d",
            "total_incidents": 2,
            "outcomes": [
                {"incident_id": "inc-001", "alert_type": "high_cpu"},
                {"incident_id": "inc-002", "alert_type": "oom_kill"},
            ],
        }

        adapter = IncidentStoreAdapter(repo)
        result = await adapter.query(period="7d")

        repo.query_incident_outcomes.assert_awaited_once_with(period="7d")
        assert result["total_incidents"] == 2
        assert len(result["outcomes"]) == 2

    @pytest.mark.asyncio
    async def test_query_default_period(self):
        repo = AsyncMock()
        repo.query_incident_outcomes.return_value = {
            "period": "30d",
            "total_incidents": 0,
            "outcomes": [],
        }

        adapter = IncidentStoreAdapter(repo)
        await adapter.query()

        repo.query_incident_outcomes.assert_awaited_once_with(period="30d")


# ── PlaybookStoreAdapter ────────────────────────────────────────


class TestPlaybookStoreAdapter:
    def _make_loader_with_playbooks(self, playbooks: list[Playbook]) -> PlaybookLoader:
        loader = PlaybookLoader(playbooks_dir=Path("/nonexistent"))
        loader._playbooks = {pb.name: pb for pb in playbooks}
        return loader

    @pytest.mark.asyncio
    async def test_list_returns_formatted_playbooks(self):
        playbooks = [
            Playbook(
                name="High CPU Remediation",
                description="Handle high CPU alerts",
                trigger=PlaybookTrigger(alert_type="high_cpu"),
            ),
            Playbook(
                name="OOM Kill Response",
                description="Handle OOM kill alerts",
                trigger=PlaybookTrigger(alert_type="oom_kill"),
            ),
        ]
        loader = self._make_loader_with_playbooks(playbooks)
        adapter = PlaybookStoreAdapter(loader)

        result = await adapter.list()

        assert result["total"] == 2
        assert len(result["playbooks"]) == 2
        assert result["playbooks"][0]["alert_type"] == "high_cpu"
        assert result["playbooks"][0]["title"] == "High CPU Remediation"
        assert result["playbooks"][1]["alert_type"] == "oom_kill"

    @pytest.mark.asyncio
    async def test_list_empty_playbooks(self):
        loader = self._make_loader_with_playbooks([])
        adapter = PlaybookStoreAdapter(loader)

        result = await adapter.list()

        assert result["total"] == 0
        assert result["playbooks"] == []


# ── LearningToolkit with Adapters ───────────────────────────────


class TestLearningToolkitWithAdapters:
    @pytest.mark.asyncio
    async def test_toolkit_uses_incident_store_adapter(self):
        repo = AsyncMock()
        repo.query_incident_outcomes.return_value = {
            "period": "30d",
            "total_incidents": 1,
            "outcomes": [{"incident_id": "inc-x", "alert_type": "disk_full"}],
        }
        adapter = IncidentStoreAdapter(repo)
        toolkit = LearningToolkit(incident_store=adapter)

        result = await toolkit.get_incident_outcomes("30d")

        assert result["total_incidents"] == 1
        assert result["outcomes"][0]["alert_type"] == "disk_full"

    @pytest.mark.asyncio
    async def test_toolkit_uses_playbook_store_adapter(self):
        playbooks = [
            Playbook(
                name="Disk Full Recovery",
                trigger=PlaybookTrigger(alert_type="disk_full"),
            )
        ]
        loader = PlaybookLoader(playbooks_dir=Path("/nonexistent"))
        loader._playbooks = {pb.name: pb for pb in playbooks}
        adapter = PlaybookStoreAdapter(loader)
        toolkit = LearningToolkit(playbook_store=adapter)

        result = await toolkit.get_current_playbooks()

        assert result["total"] == 1
        assert result["playbooks"][0]["alert_type"] == "disk_full"

    @pytest.mark.asyncio
    async def test_toolkit_falls_back_to_stubs_when_no_store(self):
        toolkit = LearningToolkit()

        result = await toolkit.get_incident_outcomes()
        assert result["total_incidents"] > 0  # Stub data

        playbooks = await toolkit.get_current_playbooks()
        assert playbooks["total"] > 0  # Stub data


# ── LearningRunner Wiring ───────────────────────────────────────


class TestLearningRunnerWiring:
    def test_runner_wires_repository_as_incident_store(self):
        repo = AsyncMock()
        runner = LearningRunner(repository=repo)

        # Toolkit should have an IncidentStoreAdapter
        assert runner._toolkit._incident_store is not None
        assert isinstance(runner._toolkit._incident_store, IncidentStoreAdapter)

    def test_runner_wires_playbook_loader_as_playbook_store(self):
        loader = PlaybookLoader(playbooks_dir=Path("/nonexistent"))
        runner = LearningRunner(playbook_loader=loader)

        assert runner._toolkit._playbook_store is not None
        assert isinstance(runner._toolkit._playbook_store, PlaybookStoreAdapter)

    def test_runner_explicit_stores_take_precedence(self):
        """Explicit incident_store/playbook_store should not be overridden."""
        custom_store = MagicMock()
        repo = AsyncMock()
        runner = LearningRunner(incident_store=custom_store, repository=repo)

        # Should use the explicit store, not the adapter
        assert runner._toolkit._incident_store is custom_store

    def test_runner_no_stores_uses_stubs(self):
        runner = LearningRunner()

        assert runner._toolkit._incident_store is None
        assert runner._toolkit._playbook_store is None


# ── Effectiveness Metrics ───────────────────────────────────────


class TestComputeEffectivenessMetrics:
    @pytest.mark.asyncio
    async def test_empty_outcomes(self):
        toolkit = LearningToolkit()
        result = await toolkit.compute_effectiveness_metrics([])

        assert result["total_incidents"] == 0
        assert result["automation_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_mixed_outcomes(self):
        outcomes = [
            {
                "alert_type": "high_cpu",
                "was_automated": True,
                "was_correct": True,
                "investigation_duration_ms": 10000,
                "remediation_duration_ms": 5000,
            },
            {
                "alert_type": "high_cpu",
                "was_automated": True,
                "was_correct": False,
                "investigation_duration_ms": 20000,
                "remediation_duration_ms": 10000,
            },
            {
                "alert_type": "oom_kill",
                "was_automated": False,
                "was_correct": True,
                "investigation_duration_ms": 30000,
                "remediation_duration_ms": 15000,
            },
        ]
        toolkit = LearningToolkit()
        result = await toolkit.compute_effectiveness_metrics(outcomes)

        assert result["total_incidents"] == 3
        assert result["automated_count"] == 2
        assert result["automation_rate"] == pytest.approx(66.67, abs=0.1)
        assert result["accuracy"] == 50.0  # 1 correct out of 2 automated
        assert result["avg_investigation_ms"] == 20000
        assert result["by_alert_type"]["high_cpu"]["count"] == 2
        assert result["by_alert_type"]["oom_kill"]["count"] == 1

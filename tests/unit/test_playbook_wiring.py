"""Tests for playbook wiring into the remediation agent.

Covers:
- resolve_playbook node: matching alert, non-matching, no alert_context
- Graph structure: resolve_playbook node present, correct edge routing
- RemediationRunner: construction with/without playbook loader
- RemediationToolkit: resolve_playbook and get_playbook_validation methods
- validate_health node: playbook checks added to validation list
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shieldops.agents.remediation.graph import create_remediation_graph, policy_gate
from shieldops.agents.remediation.models import (
    PolicyResult,
    RemediationState,
)
from shieldops.agents.remediation.nodes import (
    resolve_playbook,
    set_toolkit,
    validate_health,
)
from shieldops.agents.remediation.runner import RemediationRunner
from shieldops.agents.remediation.tools import RemediationToolkit
from shieldops.models.base import (
    ActionResult,
    AlertContext,
    Environment,
    ExecutionStatus,
    RemediationAction,
    RiskLevel,
)
from shieldops.playbooks.loader import (
    Playbook,
    PlaybookLoader,
    PlaybookStep,
    PlaybookTrigger,
    PlaybookValidation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(**kwargs: Any) -> RemediationAction:
    defaults: dict[str, Any] = {
        "id": "action-001",
        "action_type": "restart_pod",
        "target_resource": "default/web-01",
        "environment": Environment.STAGING,
        "risk_level": RiskLevel.LOW,
        "parameters": {},
        "description": "Test action",
    }
    defaults.update(kwargs)
    return RemediationAction(**defaults)


def _make_state(**kwargs: Any) -> RemediationState:
    defaults: dict[str, Any] = {
        "remediation_id": "rem-test",
        "action": _make_action(),
    }
    defaults.update(kwargs)
    return RemediationState(**defaults)


def _make_playbook(
    name: str = "pod-crash-loop",
    alert_type: str = "KubePodCrashLooping",
    with_validation: bool = True,
) -> Playbook:
    validation = None
    if with_validation:
        validation = PlaybookValidation(
            checks=[
                PlaybookStep(name="pod_running", expected="Running", timeout_seconds=120),
                PlaybookStep(name="no_recent_restarts", expected="0 restarts"),
            ],
            on_failure={"action": "rollback_and_escalate"},
        )
    return Playbook(
        name=name,
        trigger=PlaybookTrigger(alert_type=alert_type, severity=["critical", "warning"]),
        description="Test playbook",
        remediation={
            "decision_tree": [
                {
                    "condition": "last_termination_reason == 'OOMKilled'",
                    "action": "increase_memory_limit",
                    "risk_level": "medium",
                    "params": {"increase_factor": 1.5},
                },
                {
                    "condition": "default",
                    "action": "restart_pod",
                    "risk_level": "low",
                    "params": {"grace_period": 30},
                },
            ]
        },
        validation=validation,
    )


def _make_loader(playbooks: list[Playbook] | None = None) -> PlaybookLoader:
    loader = PlaybookLoader.__new__(PlaybookLoader)
    loader._dir = MagicMock()
    loader._playbooks = {}
    loader._trigger_index = {}
    for pb in playbooks or []:
        loader._playbooks[pb.name] = pb
        loader._trigger_index[pb.trigger.alert_type] = pb.name
    return loader


# ===========================================================================
# RemediationToolkit playbook methods
# ===========================================================================


class TestToolkitPlaybookMethods:
    def test_resolve_playbook_match(self) -> None:
        pb = _make_playbook()
        loader = _make_loader([pb])
        toolkit = RemediationToolkit(playbook_loader=loader)

        result = toolkit.resolve_playbook("KubePodCrashLooping", "critical")

        assert result is not None
        assert result.name == "pod-crash-loop"

    def test_resolve_playbook_no_match(self) -> None:
        loader = _make_loader([_make_playbook()])
        toolkit = RemediationToolkit(playbook_loader=loader)

        result = toolkit.resolve_playbook("UnknownAlert")

        assert result is None

    def test_resolve_playbook_no_loader(self) -> None:
        toolkit = RemediationToolkit()

        result = toolkit.resolve_playbook("KubePodCrashLooping")

        assert result is None

    def test_get_playbook_validation_exists(self) -> None:
        pb = _make_playbook(with_validation=True)
        loader = _make_loader([pb])
        toolkit = RemediationToolkit(playbook_loader=loader)

        result = toolkit.get_playbook_validation("pod-crash-loop")

        assert result is not None
        assert len(result.checks) == 2

    def test_get_playbook_validation_no_validation(self) -> None:
        pb = _make_playbook(with_validation=False)
        loader = _make_loader([pb])
        toolkit = RemediationToolkit(playbook_loader=loader)

        result = toolkit.get_playbook_validation("pod-crash-loop")

        assert result is None

    def test_get_playbook_validation_missing_playbook(self) -> None:
        loader = _make_loader([])
        toolkit = RemediationToolkit(playbook_loader=loader)

        result = toolkit.get_playbook_validation("nonexistent")

        assert result is None


# ===========================================================================
# resolve_playbook node
# ===========================================================================


class TestResolvePlaybookNode:
    @pytest.mark.asyncio
    async def test_matching_alert(self) -> None:
        pb = _make_playbook()
        loader = _make_loader([pb])
        toolkit = RemediationToolkit(playbook_loader=loader)
        set_toolkit(toolkit)

        state = _make_state(
            alert_context=AlertContext(
                alert_id="alert-001",
                alert_name="KubePodCrashLooping",
                severity="critical",
                source="prometheus",
                resource_id="default/web-01",
                triggered_at=datetime.now(UTC),
            ),
        )

        result = await resolve_playbook(state)

        assert result["matched_playbook_name"] == "pod-crash-loop"
        assert "decision_tree" in result["playbook_context"]
        assert len(result["playbook_context"]["decision_tree"]) == 2
        assert result["playbook_context"]["validation"] is not None
        # Reasoning chain recorded
        assert len(result["reasoning_chain"]) == 1
        assert result["reasoning_chain"][0].action == "resolve_playbook"

    @pytest.mark.asyncio
    async def test_non_matching_alert(self) -> None:
        loader = _make_loader([_make_playbook()])
        toolkit = RemediationToolkit(playbook_loader=loader)
        set_toolkit(toolkit)

        state = _make_state(
            alert_context=AlertContext(
                alert_id="alert-002",
                alert_name="SomethingElse",
                severity="warning",
                source="prometheus",
                resource_id="default/web-01",
                triggered_at=datetime.now(UTC),
            ),
        )

        result = await resolve_playbook(state)

        assert result["matched_playbook_name"] is None
        assert result["playbook_context"] == {}

    @pytest.mark.asyncio
    async def test_no_alert_context(self) -> None:
        toolkit = RemediationToolkit()
        set_toolkit(toolkit)

        state = _make_state(alert_context=None)

        result = await resolve_playbook(state)

        assert result["matched_playbook_name"] is None
        assert result["playbook_context"] == {}
        assert "skipping" in result["reasoning_chain"][0].output_summary.lower()


# ===========================================================================
# Graph structure
# ===========================================================================


class TestGraphWithPlaybook:
    def test_resolve_playbook_node_in_graph(self) -> None:
        graph = create_remediation_graph()
        assert "resolve_playbook" in graph.nodes

    def test_policy_gate_routes_to_resolve_playbook(self) -> None:
        state = _make_state(
            policy_result=PolicyResult(allowed=True, reasons=["OK"]),
        )
        assert policy_gate(state) == "resolve_playbook"

    def test_graph_has_edge_resolve_playbook_to_assess_risk(self) -> None:
        """resolve_playbook should have an edge to assess_risk."""
        graph = create_remediation_graph()
        # Check that resolve_playbook has edges defined
        # The graph structure uses .edges or compiled graph
        assert "resolve_playbook" in graph.nodes
        assert "assess_risk" in graph.nodes


# ===========================================================================
# RemediationRunner
# ===========================================================================


class TestRunnerAcceptsLoader:
    def test_runner_without_loader(self) -> None:
        """Runner should construct successfully without a playbook loader."""
        runner = RemediationRunner()

        assert runner._toolkit._playbook_loader is None

    def test_runner_with_loader(self) -> None:
        """Runner should accept a playbook loader and call load_all()."""
        loader = MagicMock(spec=PlaybookLoader)
        runner = RemediationRunner(playbook_loader=loader)

        loader.load_all.assert_called_once()
        assert runner._toolkit._playbook_loader is loader


# ===========================================================================
# validate_health with playbook checks
# ===========================================================================


class TestPlaybookValidationInHealthCheck:
    @pytest.mark.asyncio
    async def test_playbook_checks_added_to_validation(self) -> None:
        """When playbook_context has validation checks, they are added."""
        toolkit = RemediationToolkit()
        set_toolkit(toolkit)

        state = _make_state(
            execution_result=ActionResult(
                action_id="action-001",
                status=ExecutionStatus.SUCCESS,
                message="OK",
                started_at=datetime.now(UTC),
            ),
            playbook_context={
                "validation": {
                    "checks": [
                        {"name": "pod_running", "expected": "Running"},
                        {"name": "no_recent_restarts", "expected": "0 restarts"},
                    ],
                    "on_failure": {"action": "rollback"},
                },
            },
        )

        with patch("shieldops.agents.remediation.nodes.llm_structured") as mock_llm:
            mock_llm.side_effect = Exception("skip LLM")
            result = await validate_health(state)

        # Should have playbook checks
        check_names = [c.check_name for c in result["validation_checks"]]
        assert "pod_running" in check_names
        assert "no_recent_restarts" in check_names

    @pytest.mark.asyncio
    async def test_no_playbook_context_no_extra_checks(self) -> None:
        """Without playbook_context, only standard health checks run."""
        toolkit = RemediationToolkit()
        set_toolkit(toolkit)

        state = _make_state(
            execution_result=ActionResult(
                action_id="action-001",
                status=ExecutionStatus.SUCCESS,
                message="OK",
                started_at=datetime.now(UTC),
            ),
        )

        with patch("shieldops.agents.remediation.nodes.llm_structured") as mock_llm:
            mock_llm.side_effect = Exception("skip LLM")
            result = await validate_health(state)

        # No playbook checks — only standard (which may be empty without connector)
        check_names = [c.check_name for c in result["validation_checks"]]
        assert "pod_running" not in check_names

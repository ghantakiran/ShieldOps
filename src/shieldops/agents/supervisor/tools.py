"""Tool functions for the Supervisor Agent.

Bridges specialist agent runners, notification channels, and
event classification into the supervisor orchestration workflow.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.supervisor.models import DelegatedTask, TaskStatus, TaskType

logger = structlog.get_logger()


# Type alias for agent runner callables
AgentRunner = Any


class SupervisorToolkit:
    """Encapsulates external integrations for the supervisor.

    Holds references to specialist agent runners and notification
    channels, allowing production and test configurations.
    """

    def __init__(
        self,
        agent_runners: dict[str, AgentRunner] | None = None,
        notification_channels: dict[str, Any] | None = None,
        playbook_loader: Any = None,
    ) -> None:
        self._runners = agent_runners or {}
        self._channels = notification_channels or {}
        self._playbook_loader = playbook_loader

    def classify_event_rules(self, event: dict[str, Any]) -> dict[str, Any]:
        """Rule-based event classification as a baseline before LLM.

        Enriches classification with matching playbook metadata when available.
        Returns a preliminary classification that the LLM can refine.
        """
        event_type = event.get("type", "")
        severity = event.get("severity", "medium")
        alert_name = event.get("alert_name", "")

        # Check for matching playbook
        playbook_match = None
        if self._playbook_loader and alert_name:
            playbook_match = self._playbook_loader.match(alert_name, severity)

        # Rule-based mapping
        type_map: dict[str, tuple[str, str]] = {
            "alert": ("investigate", "high"),
            "incident": ("investigate", "critical"),
            "remediation_request": ("remediate", "high"),
            "auto_heal": ("remediate", "medium"),
            "cve_alert": ("security_scan", "high"),
            "compliance_drift": ("security_scan", "medium"),
            "credential_expiry": ("security_scan", "high"),
            "cost_anomaly": ("cost_analysis", "medium"),
            "budget_alert": ("cost_analysis", "high"),
            "incident_resolved": ("learn", "low"),
            "feedback": ("learn", "low"),
            "schedule_scan": ("security_scan", "low"),
            "schedule_cost": ("cost_analysis", "low"),
        }

        if event_type in type_map:
            task_type, priority = type_map[event_type]
        else:
            task_type = "investigate"
            priority = severity

        result = {
            "task_type": task_type,
            "priority": priority,
            "confidence": 1.0 if event_type in type_map else 0.6,
            "reasoning": f"Rule-based classification for event type '{event_type}'",
        }

        # Enrich with playbook metadata if matched
        if playbook_match:
            result["playbook"] = {
                "name": playbook_match.name,
                "description": playbook_match.description,
                "decision_tree": [c.model_dump() for c in playbook_match.decision_tree],
            }
            result["reasoning"] += f" | Matched playbook: {playbook_match.name}"

        return result

    async def dispatch_task(
        self,
        task_type: TaskType,
        input_data: dict[str, Any],
    ) -> DelegatedTask:
        """Dispatch a task to the appropriate specialist agent.

        If a runner is registered for the task type, it will be invoked.
        Otherwise, returns a simulated completion.
        """
        agent_name = _task_type_to_agent(task_type)
        task_id = f"sup-{uuid4().hex[:12]}"
        now = datetime.now(UTC)

        task = DelegatedTask(
            task_id=task_id,
            task_type=task_type,
            agent_name=agent_name,
            status=TaskStatus.IN_PROGRESS,
            input_data=input_data,
            started_at=now,
        )

        runner = self._runners.get(agent_name)
        if runner:
            try:
                result = await runner.run(input_data)
                task.status = TaskStatus.COMPLETED
                task.result = result if isinstance(result, dict) else {"data": str(result)}
                task.completed_at = datetime.now(UTC)
                task.duration_ms = int((task.completed_at - now).total_seconds() * 1000)
            except Exception as e:
                logger.error("agent_dispatch_failed", agent=agent_name, error=str(e))
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now(UTC)
                task.duration_ms = int((task.completed_at - now).total_seconds() * 1000)
        else:
            # Simulated completion when no runner configured
            task.status = TaskStatus.COMPLETED
            task.result = {
                "simulated": True,
                "agent": agent_name,
                "message": f"No runner configured for {agent_name}. Task simulated as complete.",
            }
            task.completed_at = datetime.now(UTC)
            task.duration_ms = int((task.completed_at - now).total_seconds() * 1000)

        return task

    async def send_escalation(
        self,
        channel: str,
        message: str,
        urgency: str = "soon",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an escalation notification to a channel.

        Returns notification result with delivery status.
        """
        notifier = self._channels.get(channel)
        if notifier:
            try:
                return await notifier.send(message=message, urgency=urgency, metadata=metadata)
            except Exception as e:
                logger.error("escalation_send_failed", channel=channel, error=str(e))

        # Simulated notification when no channel configured
        logger.info(
            "escalation_sent",
            channel=channel,
            urgency=urgency,
            message=message[:100],
        )
        return {
            "delivered": True,
            "channel": channel,
            "simulated": notifier is None,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def evaluate_chain_rules(
        self,
        completed_task: DelegatedTask,
    ) -> dict[str, Any]:
        """Rule-based evaluation of whether to chain a follow-up task.

        Returns chaining recommendation based on task outcome.
        """
        if completed_task.status != TaskStatus.COMPLETED or not completed_task.result:
            return {
                "should_chain": False,
                "chain_task_type": "none",
                "reasoning": "Task did not complete successfully",
            }

        result = completed_task.result

        # Investigation → Remediation if high confidence + recommended action
        if completed_task.task_type == TaskType.INVESTIGATE:
            confidence = result.get("confidence_score", 0)
            has_action = result.get("recommended_action") is not None
            if confidence >= 0.85 and has_action:
                return {
                    "should_chain": True,
                    "chain_task_type": "remediate",
                    "reasoning": (
                        f"Investigation confidence {confidence:.0%} with recommended action"
                    ),
                }

        # Remediation → Learning to record outcome
        if completed_task.task_type == TaskType.REMEDIATE:
            return {
                "should_chain": True,
                "chain_task_type": "learn",
                "reasoning": "Record remediation outcome for continuous improvement",
            }

        # Security scan with critical CVEs → Remediation
        if completed_task.task_type == TaskType.SECURITY_SCAN:
            critical = result.get("critical_cves", 0)
            if critical > 0:
                return {
                    "should_chain": True,
                    "chain_task_type": "remediate",
                    "reasoning": f"{critical} critical CVEs found — triggering remediation",
                }

        return {"should_chain": False, "chain_task_type": "none", "reasoning": "No chaining needed"}

    def evaluate_escalation_rules(
        self,
        completed_task: DelegatedTask,
        classification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Rule-based evaluation of whether to escalate to a human.

        Returns escalation recommendation.
        """
        # Failed task on critical priority
        if completed_task.status == TaskStatus.FAILED:
            priority = (classification or {}).get("priority", "medium")
            if priority in ("critical", "high"):
                return {
                    "needs_escalation": True,
                    "reason": f"Agent failed on {priority} priority task: {completed_task.error}",
                    "channel": "pagerduty" if priority == "critical" else "slack",
                    "urgency": "immediate" if priority == "critical" else "soon",
                }

        # Low confidence classification on high-priority event
        if classification:
            confidence = classification.get("confidence", 1.0)
            priority = classification.get("priority", "medium")
            if confidence < 0.5 and priority in ("critical", "high"):
                return {
                    "needs_escalation": True,
                    "reason": (
                        f"Low confidence ({confidence:.0%}) classification on {priority} event"
                    ),
                    "channel": "slack",
                    "urgency": "soon",
                }

        return {
            "needs_escalation": False,
            "reason": "No escalation needed",
            "channel": "slack",
            "urgency": "informational",
        }


def _task_type_to_agent(task_type: TaskType) -> str:
    """Map task type to agent name."""
    return {
        TaskType.INVESTIGATE: "investigation",
        TaskType.REMEDIATE: "remediation",
        TaskType.SECURITY_SCAN: "security",
        TaskType.COST_ANALYSIS: "cost",
        TaskType.LEARN: "learning",
    }.get(task_type, "investigation")

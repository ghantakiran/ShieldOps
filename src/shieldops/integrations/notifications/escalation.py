"""Notification escalation engine with retry and fallback chains.

If a notification to the primary channel fails, the engine escalates
through ordered steps — each with its own retry policy and delay.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Models ───────────────────────────────────────────────────────────


class EscalationStep(BaseModel):
    """Single step in an escalation chain."""

    channel: str
    delay_seconds: int = 0
    retry_count: int = 2
    retry_delay_seconds: int = 5
    condition: str = ""  # optional condition expression


class EscalationPolicy(BaseModel):
    """Ordered escalation chain for a severity level."""

    name: str
    description: str = ""
    steps: list[EscalationStep] = Field(default_factory=list)
    max_duration_seconds: int = 300
    severity_filter: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class EscalationAttempt(BaseModel):
    channel: str
    attempt: int
    success: bool
    error: str = ""
    timestamp: float = Field(default_factory=time.time)


class EscalationResult(BaseModel):
    """Outcome of executing an escalation policy."""

    execution_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    policy_name: str
    delivered: bool = False
    channel_used: str = ""
    attempts: list[EscalationAttempt] = Field(default_factory=list)
    escalated: bool = False
    duration_ms: float = 0.0
    started_at: float = Field(default_factory=time.time)


# ── Engine ───────────────────────────────────────────────────────────


class EscalationEngine:
    """Execute ordered escalation chains with retry/fallback.

    Parameters
    ----------
    dispatcher:
        A ``NotificationDispatcher`` (or compatible) instance.
    default_timeout:
        Max seconds for an entire escalation execution.
    max_retries:
        Default max retries per step (overridden by step config).
    """

    def __init__(
        self,
        dispatcher: Any = None,
        default_timeout: int = 300,
        max_retries: int = 3,
    ) -> None:
        self._dispatcher = dispatcher
        self._policies: dict[str, EscalationPolicy] = {}
        self._default_timeout = default_timeout
        self._max_retries = max_retries
        self._history: list[EscalationResult] = []

    # ── Policy CRUD ──────────────────────────────────────────────

    def register_policy(self, policy: EscalationPolicy) -> EscalationPolicy:
        policy.updated_at = time.time()
        self._policies[policy.name] = policy
        logger.info("escalation_policy_registered", name=policy.name)
        return policy

    def get_policy(self, name: str) -> EscalationPolicy | None:
        return self._policies.get(name)

    def delete_policy(self, name: str) -> bool:
        return self._policies.pop(name, None) is not None

    def list_policies(self) -> list[EscalationPolicy]:
        return list(self._policies.values())

    def update_policy(self, name: str, updates: dict[str, Any]) -> EscalationPolicy | None:
        policy = self._policies.get(name)
        if policy is None:
            return None
        for k, v in updates.items():
            if hasattr(policy, k) and k != "name":
                setattr(policy, k, v)
        policy.updated_at = time.time()
        return policy

    # ── Execution ────────────────────────────────────────────────

    async def execute(
        self,
        policy_name: str,
        message: str,
        severity: str = "info",
        details: dict[str, Any] | None = None,
    ) -> EscalationResult:
        """Execute an escalation policy, trying each step in order."""
        policy = self._policies.get(policy_name)
        if policy is None:
            return EscalationResult(policy_name=policy_name, delivered=False)

        if not policy.enabled:
            return EscalationResult(policy_name=policy_name, delivered=False)

        start = time.time()
        result = EscalationResult(policy_name=policy_name)
        timeout = policy.max_duration_seconds or self._default_timeout

        for step_idx, step in enumerate(policy.steps):
            # Check timeout
            elapsed = time.time() - start
            if elapsed >= timeout:
                logger.warning("escalation_timeout", policy=policy_name)
                break

            # Delay before this step (skip for first step)
            if step.delay_seconds > 0 and step_idx > 0:
                await asyncio.sleep(min(step.delay_seconds, timeout - elapsed))

            # Try this step with retries
            delivered = await self._try_step(step, message, severity, details, result)
            if delivered:
                result.delivered = True
                result.channel_used = step.channel
                result.escalated = step_idx > 0
                break

        result.duration_ms = round((time.time() - start) * 1000, 2)

        # Keep history bounded
        self._history.append(result)
        if len(self._history) > 1000:
            self._history = self._history[-500:]

        return result

    async def _try_step(
        self,
        step: EscalationStep,
        message: str,
        severity: str,
        details: dict[str, Any] | None,
        result: EscalationResult,
    ) -> bool:
        """Try sending via a step's channel with retries."""
        retries = min(step.retry_count, self._max_retries)
        for attempt_num in range(retries + 1):
            try:
                if self._dispatcher is None:
                    raise RuntimeError("No dispatcher configured")  # noqa: TRY301
                ok = await self._dispatcher.send(
                    channel=step.channel,
                    message=message,
                    severity=severity,
                    details=details,
                )
                result.attempts.append(
                    EscalationAttempt(
                        channel=step.channel,
                        attempt=attempt_num + 1,
                        success=ok,
                    )
                )
                if ok:
                    return True
            except Exception as exc:
                result.attempts.append(
                    EscalationAttempt(
                        channel=step.channel,
                        attempt=attempt_num + 1,
                        success=False,
                        error=str(exc),
                    )
                )
            # Wait before retry
            if attempt_num < retries:
                await asyncio.sleep(step.retry_delay_seconds)
        return False

    async def execute_for_severity(
        self,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> EscalationResult | None:
        """Find and execute the first policy matching *severity*."""
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if not policy.severity_filter or severity in policy.severity_filter:
                return await self.execute(policy.name, message, severity, details)
        return None

    async def test_policy(self, policy_name: str) -> EscalationResult:
        """Dry-run test of a policy with a test message."""
        return await self.execute(
            policy_name,
            message="[TEST] Escalation policy test notification",
            severity="info",
            details={"test": True},
        )

    # ── History / Stats ──────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[EscalationResult]:
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._history)
        delivered = sum(1 for r in self._history if r.delivered)
        escalated = sum(1 for r in self._history if r.escalated)
        return {
            "total_policies": len(self._policies),
            "total_executions": total,
            "delivered": delivered,
            "failed": total - delivered,
            "escalated": escalated,
            "delivery_rate": round(delivered / total * 100, 2) if total else 0.0,
        }

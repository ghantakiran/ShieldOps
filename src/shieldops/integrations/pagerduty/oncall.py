"""On-call resolution via PagerDuty — maps services to teams and on-call users.

Provides helper functions that combine PagerDuty service lookups with
escalation policy resolution to determine who is on-call for a given
service right now.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from shieldops.integrations.pagerduty.client import PagerDutyClient, PagerDutyUser

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EscalationLevel(BaseModel):
    """A single level in an escalation chain."""

    level: int
    users: list[PagerDutyUser] = Field(default_factory=list)


class ServiceOwnership(BaseModel):
    """Maps a service to its owning team and on-call users."""

    service_id: str
    service_name: str
    escalation_policy_id: str = ""
    escalation_policy_name: str = ""
    oncall_users: list[PagerDutyUser] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class OnCallResolver:
    """Resolve on-call responders for PagerDuty services.

    Parameters
    ----------
    client:
        An initialised :class:`PagerDutyClient`.
    """

    def __init__(self, client: PagerDutyClient) -> None:
        self._client = client

    async def resolve_oncall_for_service(self, service_id: str) -> list[PagerDutyUser]:
        """Find the currently on-call person(s) for a specific service.

        Looks up the service's escalation policy and then queries the
        PagerDuty on-call endpoint for the first escalation level.
        """
        try:
            service = await self._client.get_service(service_id)
            if not service.escalation_policy_id:
                logger.warning(
                    "pagerduty_no_escalation_policy",
                    service_id=service_id,
                )
                return []

            users = await self._client.get_oncall_users(
                escalation_policy_ids=[service.escalation_policy_id],
            )
            logger.info(
                "oncall_resolved_for_service",
                service_id=service_id,
                service_name=service.name,
                user_count=len(users),
            )
            return users
        except Exception as exc:
            logger.error(
                "oncall_resolve_failed",
                service_id=service_id,
                error=str(exc),
            )
            return []

    async def resolve_escalation_chain(
        self,
        service_id: str,
    ) -> list[EscalationLevel]:
        """Return the ordered escalation chain for a service.

        Queries the PagerDuty escalation policy rules and resolves
        users at each level.
        """
        try:
            service = await self._client.get_service(service_id)
            if not service.escalation_policy_id:
                return []

            # Fetch the escalation policy details directly.
            data = await self._client._request(  # noqa: SLF001
                "GET",
                f"/escalation_policies/{service.escalation_policy_id}",
            )
            policy = data.get("escalation_policy", {})
            rules = policy.get("escalation_rules", [])

            chain: list[EscalationLevel] = []
            for idx, rule in enumerate(rules):
                targets = rule.get("targets", [])
                users: list[PagerDutyUser] = []
                for target in targets:
                    if target.get("type") in ("user_reference", "user"):
                        users.append(
                            PagerDutyUser(
                                id=target.get("id", ""),
                                name=target.get("summary", ""),
                                email="",
                                html_url=target.get("html_url", ""),
                            )
                        )
                    elif target.get("type") in ("schedule_reference", "schedule"):
                        schedule_users = await self._client.get_oncall_users(
                            schedule_ids=[target.get("id", "")],
                        )
                        users.extend(schedule_users)
                chain.append(EscalationLevel(level=idx + 1, users=users))

            logger.info(
                "escalation_chain_resolved",
                service_id=service_id,
                levels=len(chain),
            )
            return chain
        except Exception as exc:
            logger.error(
                "escalation_chain_failed",
                service_id=service_id,
                error=str(exc),
            )
            return []

    async def get_service_ownership(
        self,
        service_ids: list[str],
    ) -> dict[str, ServiceOwnership]:
        """Map multiple services to their teams and on-call users.

        Returns a dictionary keyed by service_id.
        """
        result: dict[str, ServiceOwnership] = {}
        for sid in service_ids:
            try:
                service = await self._client.get_service(sid)
                oncall = await self.resolve_oncall_for_service(sid)
                result[sid] = ServiceOwnership(
                    service_id=sid,
                    service_name=service.name,
                    escalation_policy_id=service.escalation_policy_id,
                    escalation_policy_name=service.escalation_policy_name,
                    oncall_users=oncall,
                )
            except Exception as exc:
                logger.error(
                    "service_ownership_failed",
                    service_id=sid,
                    error=str(exc),
                )
                result[sid] = ServiceOwnership(
                    service_id=sid,
                    service_name="",
                )
        return result

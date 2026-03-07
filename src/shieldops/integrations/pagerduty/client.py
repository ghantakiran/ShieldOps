"""PagerDuty REST API v2 client for incident management and on-call resolution.

Provides async methods for querying services, on-call schedules, and managing
incidents through the PagerDuty REST API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

PAGERDUTY_API_BASE = "https://api.pagerduty.com"

# Maximum retries for transient failures.
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = [0.5, 1.0, 2.0]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PagerDutyUser(BaseModel):
    """A PagerDuty user with contact info."""

    id: str
    name: str
    email: str
    html_url: str = ""
    role: str = ""


class PagerDutyService(BaseModel):
    """A PagerDuty service with escalation policy."""

    id: str
    name: str
    description: str = ""
    status: str = ""
    html_url: str = ""
    escalation_policy_id: str = ""
    escalation_policy_name: str = ""


class PagerDutyIncident(BaseModel):
    """A PagerDuty incident."""

    id: str
    incident_number: int = 0
    title: str = ""
    status: str = ""
    urgency: str = ""
    service_id: str = ""
    service_name: str = ""
    html_url: str = ""
    created_at: str = ""
    assignments: list[dict[str, Any]] = Field(default_factory=list)


class PagerDutyNote(BaseModel):
    """A note on a PagerDuty incident."""

    id: str
    content: str
    created_at: str = ""
    user_id: str = ""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class PagerDutyClient:
    """Async client for PagerDuty REST API v2.

    Parameters
    ----------
    api_key:
        PagerDuty REST API token.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(self, api_key: str, *, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    # ------------------------------------------------------------------
    # On-call
    # ------------------------------------------------------------------

    async def get_oncall_users(
        self,
        schedule_ids: list[str] | None = None,
        escalation_policy_ids: list[str] | None = None,
    ) -> list[PagerDutyUser]:
        """Return the currently on-call users for the given schedules or policies."""
        params: dict[str, Any] = {"time_zone": "UTC"}
        if schedule_ids:
            params["schedule_ids[]"] = schedule_ids
        if escalation_policy_ids:
            params["escalation_policy_ids[]"] = escalation_policy_ids

        data = await self._request("GET", "/oncalls", params=params)
        oncalls = data.get("oncalls", [])

        seen: set[str] = set()
        users: list[PagerDutyUser] = []
        for entry in oncalls:
            user_data = entry.get("user", {})
            uid = user_data.get("id", "")
            if uid and uid not in seen:
                seen.add(uid)
                users.append(
                    PagerDutyUser(
                        id=uid,
                        name=user_data.get("name", ""),
                        email=user_data.get("email", ""),
                        html_url=user_data.get("html_url", ""),
                    )
                )
        logger.info(
            "pagerduty_oncall_resolved",
            user_count=len(users),
            schedule_ids=schedule_ids,
        )
        return users

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    async def get_service(self, service_id: str) -> PagerDutyService:
        """Fetch a single service by ID, including its escalation policy."""
        data = await self._request(
            "GET",
            f"/services/{service_id}",
            params={"include[]": ["escalation_policies"]},
        )
        svc = data.get("service", {})
        ep = svc.get("escalation_policy", {})
        return PagerDutyService(
            id=svc.get("id", service_id),
            name=svc.get("name", ""),
            description=svc.get("description", ""),
            status=svc.get("status", ""),
            html_url=svc.get("html_url", ""),
            escalation_policy_id=ep.get("id", ""),
            escalation_policy_name=ep.get("summary", ""),
        )

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    async def get_incidents(
        self,
        service_ids: list[str] | None = None,
        statuses: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 25,
    ) -> list[PagerDutyIncident]:
        """List incidents, optionally filtering by service, status, and time."""
        params: dict[str, Any] = {"limit": min(limit, 100), "sort_by": "created_at:desc"}
        if service_ids:
            params["service_ids[]"] = service_ids
        if statuses:
            params["statuses[]"] = statuses
        else:
            params["statuses[]"] = ["triggered", "acknowledged"]
        if since:
            params["since"] = since.astimezone(UTC).isoformat()

        data = await self._request("GET", "/incidents", params=params)
        incidents: list[PagerDutyIncident] = []
        for raw in data.get("incidents", []):
            svc = raw.get("service", {})
            incidents.append(
                PagerDutyIncident(
                    id=raw.get("id", ""),
                    incident_number=raw.get("incident_number", 0),
                    title=raw.get("title", ""),
                    status=raw.get("status", ""),
                    urgency=raw.get("urgency", ""),
                    service_id=svc.get("id", ""),
                    service_name=svc.get("summary", ""),
                    html_url=raw.get("html_url", ""),
                    created_at=raw.get("created_at", ""),
                    assignments=raw.get("assignments", []),
                )
            )
        logger.info("pagerduty_incidents_fetched", count=len(incidents))
        return incidents

    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Acknowledge an incident."""
        return await self._update_incident_status(incident_id, "acknowledged")

    async def resolve_incident(self, incident_id: str) -> bool:
        """Resolve an incident."""
        return await self._update_incident_status(incident_id, "resolved")

    async def create_incident(
        self,
        service_id: str,
        title: str,
        body: str = "",
        urgency: str = "high",
    ) -> PagerDutyIncident | None:
        """Create a new incident on a service."""
        payload: dict[str, Any] = {
            "incident": {
                "type": "incident",
                "title": title,
                "urgency": urgency,
                "service": {"id": service_id, "type": "service_reference"},
            }
        }
        if body:
            payload["incident"]["body"] = {"type": "incident_body", "details": body}

        data = await self._request("POST", "/incidents", json_body=payload)
        raw = data.get("incident")
        if not raw:
            logger.error("pagerduty_create_incident_failed", service_id=service_id)
            return None

        svc = raw.get("service", {})
        incident = PagerDutyIncident(
            id=raw.get("id", ""),
            incident_number=raw.get("incident_number", 0),
            title=raw.get("title", ""),
            status=raw.get("status", ""),
            urgency=raw.get("urgency", ""),
            service_id=svc.get("id", ""),
            service_name=svc.get("summary", ""),
            html_url=raw.get("html_url", ""),
            created_at=raw.get("created_at", ""),
        )
        logger.info(
            "pagerduty_incident_created",
            incident_id=incident.id,
            title=title,
        )
        return incident

    async def add_note(self, incident_id: str, content: str) -> PagerDutyNote | None:
        """Add a timeline note to an incident."""
        payload = {"note": {"content": content}}
        data = await self._request(
            "POST",
            f"/incidents/{incident_id}/notes",
            json_body=payload,
        )
        raw = data.get("note")
        if not raw:
            logger.warning("pagerduty_add_note_failed", incident_id=incident_id)
            return None
        note = PagerDutyNote(
            id=raw.get("id", ""),
            content=raw.get("content", ""),
            created_at=raw.get("created_at", ""),
            user_id=raw.get("user", {}).get("id", ""),
        )
        logger.info("pagerduty_note_added", incident_id=incident_id)
        return note

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _update_incident_status(self, incident_id: str, status: str) -> bool:
        """PUT an incident status update."""
        payload = {"incident": {"type": "incident_reference", "status": status}}
        try:
            await self._request("PUT", f"/incidents/{incident_id}", json_body=payload)
            logger.info(
                "pagerduty_incident_updated",
                incident_id=incident_id,
                status=status,
            )
            return True
        except PagerDutyAPIError:
            return False

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request against the PagerDuty REST API with retries."""
        url = f"{PAGERDUTY_API_BASE}{path}"
        headers = {
            "Authorization": f"Token token={self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        json=json_body,
                    )
                if resp.status_code == 429:
                    # Rate-limited — back off and retry.
                    import asyncio

                    backoff = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                    logger.warning(
                        "pagerduty_rate_limited",
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "pagerduty_api_error",
                        status=resp.status_code,
                        body=resp.text[:300],
                        path=path,
                    )
                    raise PagerDutyAPIError(
                        f"PagerDuty API {method} {path} returned {resp.status_code}"
                    )

                return resp.json()  # type: ignore[no-any-return]

            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "pagerduty_http_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < _MAX_RETRIES - 1:
                    import asyncio

                    await asyncio.sleep(
                        _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                    )

        raise PagerDutyAPIError(f"PagerDuty request failed after {_MAX_RETRIES} retries") from (
            last_exc
        )


class PagerDutyAPIError(Exception):
    """Raised when a PagerDuty API call fails after retries."""

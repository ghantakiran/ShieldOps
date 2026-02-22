"""ServiceNow ITSM integration — incidents and change requests.

Provides an async client for the ServiceNow Table API, with bidirectional
state mapping between ShieldOps incidents/remediations and ServiceNow
incidents/change requests.  Supports webhook ingestion for real-time
status sync.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger()

# ── ServiceNow incident states ────────────────────────────────────────
# https://docs.servicenow.com/bundle/utah-it-service-management/page/
#   product/incident-management/reference/r_IncidentStates.html


class IncidentState(IntEnum):
    NEW = 1
    IN_PROGRESS = 2
    ON_HOLD = 3
    RESOLVED = 6
    CLOSED = 7


# ── State mappings ────────────────────────────────────────────────────

SHIELDOPS_TO_SNOW_STATE: dict[str, int] = {
    "open": IncidentState.NEW,
    "investigating": IncidentState.IN_PROGRESS,
    "resolved": IncidentState.RESOLVED,
    "closed": IncidentState.CLOSED,
}

SNOW_TO_SHIELDOPS_STATE: dict[int, str] = {
    IncidentState.NEW: "open",
    IncidentState.IN_PROGRESS: "investigating",
    IncidentState.ON_HOLD: "investigating",
    IncidentState.RESOLVED: "resolved",
    IncidentState.CLOSED: "closed",
}

URGENCY_MAP: dict[str, int] = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}

# ── Pydantic configuration models ────────────────────────────────────


class ServiceNowConfig(BaseModel):
    """Connection and mapping configuration for a ServiceNow instance."""

    instance_url: str
    username: str
    password: str
    incident_table: str = "incident"
    change_table: str = "change_request"
    urgency_mapping: dict[str, int] = Field(default_factory=lambda: dict(URGENCY_MAP))
    state_mapping: dict[str, int] = Field(default_factory=lambda: dict(SHIELDOPS_TO_SNOW_STATE))

    @field_validator("instance_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class ServiceNowRecord(BaseModel):
    """Lightweight representation of a ServiceNow record."""

    sys_id: str = ""
    number: str = ""
    short_description: str = ""
    state: str = ""
    priority: str = ""
    created_on: str = ""
    updated_on: str = ""


# ── Exceptions ────────────────────────────────────────────────────────


class ServiceNowError(Exception):
    """Base exception for ServiceNow API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ServiceNowAuthError(ServiceNowError):
    """Authentication failure (401/403)."""


class ServiceNowNotFoundError(ServiceNowError):
    """Record not found (404)."""


# ── Client ────────────────────────────────────────────────────────────


class ServiceNowClient:
    """Async client for the ServiceNow Table API.

    Uses HTTP Basic authentication and ``httpx.AsyncClient`` for all
    requests.  The client is lazily initialised on first use and can be
    explicitly closed via :meth:`close`.

    Args:
        instance_url: Full URL of the ServiceNow instance
            (e.g. ``https://mycompany.service-now.com``).
        username: ServiceNow integration user name.
        password: ServiceNow integration user password.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        instance_url: str,
        username: str,
        password: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_client(self) -> httpx.AsyncClient:
        """Lazily create the underlying ``httpx.AsyncClient``."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._instance_url,
                auth=(self._username, self._password),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Low-level request helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request against the ServiceNow Table API.

        Raises:
            ServiceNowAuthError: on 401/403 responses.
            ServiceNowNotFoundError: on 404 responses.
            ServiceNowError: on any other non-2xx response.
        """
        client = self._ensure_client()

        try:
            response = await client.request(method, path, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise ServiceNowError(f"Request timed out: {method} {path}", status_code=None) from exc
        except httpx.HTTPError as exc:
            raise ServiceNowError(f"HTTP error: {exc}", status_code=None) from exc

        if response.status_code in (401, 403):
            raise ServiceNowAuthError(
                f"Authentication failed ({response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code == 404:
            raise ServiceNowNotFoundError(f"Record not found: {path}", status_code=404)
        if response.status_code >= 400:
            raise ServiceNowError(
                f"ServiceNow API error {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
            )

        # DELETE or 204 No Content may return empty body
        if response.status_code == 204 or not response.content:
            return {}

        return dict(response.json())

    # ------------------------------------------------------------------
    # Incident CRUD
    # ------------------------------------------------------------------

    async def create_incident(
        self,
        short_description: str,
        description: str,
        *,
        urgency: int = 3,
        impact: int = 3,
        category: str | None = None,
        assignment_group: str | None = None,
        caller_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new ServiceNow incident.

        Returns the full ``result`` object from the ServiceNow response.
        """
        body: dict[str, Any] = {
            "short_description": short_description,
            "description": description,
            "urgency": str(urgency),
            "impact": str(impact),
        }
        if category:
            body["category"] = category
        if assignment_group:
            body["assignment_group"] = assignment_group
        if caller_id:
            body["caller_id"] = caller_id

        data = await self._request("POST", "/api/now/table/incident", json=body)
        result: dict[str, Any] = data.get("result", data)

        logger.info(
            "servicenow_incident_created",
            sys_id=result.get("sys_id"),
            number=result.get("number"),
        )
        return result

    async def update_incident(self, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Patch an existing incident by ``sys_id``."""
        data = await self._request("PATCH", f"/api/now/table/incident/{sys_id}", json=fields)
        result: dict[str, Any] = data.get("result", data)
        logger.info(
            "servicenow_incident_updated",
            sys_id=sys_id,
            fields=list(fields.keys()),
        )
        return result

    async def get_incident(self, sys_id: str) -> dict[str, Any]:
        """Fetch a single incident by ``sys_id``."""
        data = await self._request("GET", f"/api/now/table/incident/{sys_id}")
        result: dict[str, Any] = data.get("result", data)
        return result

    async def close_incident(
        self,
        sys_id: str,
        close_code: str = "Solved",
        close_notes: str = "",
    ) -> dict[str, Any]:
        """Resolve and close an incident (state = 7 / Closed)."""
        fields: dict[str, Any] = {
            "state": str(IncidentState.CLOSED),
            "close_code": close_code,
            "close_notes": close_notes or "Closed by ShieldOps automation",
        }
        result = await self.update_incident(sys_id, fields)
        logger.info("servicenow_incident_closed", sys_id=sys_id)
        return result

    # ------------------------------------------------------------------
    # Change Request CRUD
    # ------------------------------------------------------------------

    async def create_change_request(
        self,
        short_description: str,
        description: str,
        *,
        type: str = "normal",
        risk: str = "moderate",
        impact: int = 3,
        assignment_group: str | None = None,
    ) -> dict[str, Any]:
        """Create a new ServiceNow change request."""
        body: dict[str, Any] = {
            "short_description": short_description,
            "description": description,
            "type": type,
            "risk": risk,
            "impact": str(impact),
        }
        if assignment_group:
            body["assignment_group"] = assignment_group

        data = await self._request("POST", "/api/now/table/change_request", json=body)
        result: dict[str, Any] = data.get("result", data)
        logger.info(
            "servicenow_change_created",
            sys_id=result.get("sys_id"),
            number=result.get("number"),
        )
        return result

    async def update_change_request(self, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Patch an existing change request by ``sys_id``."""
        data = await self._request("PATCH", f"/api/now/table/change_request/{sys_id}", json=fields)
        result: dict[str, Any] = data.get("result", data)
        logger.info(
            "servicenow_change_updated",
            sys_id=sys_id,
            fields=list(fields.keys()),
        )
        return result

    async def get_change_request(self, sys_id: str) -> dict[str, Any]:
        """Fetch a single change request by ``sys_id``."""
        data = await self._request("GET", f"/api/now/table/change_request/{sys_id}")
        result: dict[str, Any] = data.get("result", data)
        return result

    # ------------------------------------------------------------------
    # ShieldOps domain mappers
    # ------------------------------------------------------------------

    async def create_from_shieldops_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Map a ShieldOps incident to a ServiceNow incident and create it.

        Expected keys in *incident*: ``title``, ``description``,
        ``severity``, ``environment``, ``service``.
        """
        severity = incident.get("severity", "medium").lower()
        urgency = URGENCY_MAP.get(severity, 3)
        impact = URGENCY_MAP.get(severity, 3)

        description_parts = [
            incident.get("description", ""),
            f"\nEnvironment: {incident.get('environment', 'N/A')}",
            f"Service: {incident.get('service', 'N/A')}",
            f"ShieldOps ID: {incident.get('id', incident.get('incident_id', 'N/A'))}",
            f"Detected at: {incident.get('created_at', datetime.now(UTC).isoformat())}",
        ]

        return await self.create_incident(
            short_description=(
                f"[ShieldOps] {incident.get('title', incident.get('alert_name', 'Incident'))}"
            ),
            description="\n".join(description_parts),
            urgency=urgency,
            impact=impact,
            category=incident.get("category"),
            assignment_group=incident.get("assignment_group"),
        )

    async def create_change_from_remediation(self, remediation: dict[str, Any]) -> dict[str, Any]:
        """Create a ServiceNow change request from a ShieldOps remediation plan.

        Expected keys in *remediation*: ``name`` or ``action``,
        ``description``, ``risk_level``, ``environment``, ``target``.
        """
        risk_map: dict[str, str] = {
            "low": "low",
            "medium": "moderate",
            "high": "high",
            "critical": "high",
        }
        risk_level = remediation.get("risk_level", "medium").lower()

        description_parts = [
            remediation.get("description", ""),
            f"\nTarget: {remediation.get('target', 'N/A')}",
            f"Environment: {remediation.get('environment', 'N/A')}",
            f"ShieldOps Remediation ID: "
            f"{remediation.get('id', remediation.get('remediation_id', 'N/A'))}",
            f"Playbook: {remediation.get('playbook', 'N/A')}",
        ]

        severity = remediation.get("risk_level", "medium").lower()
        impact = URGENCY_MAP.get(severity, 3)

        return await self.create_change_request(
            short_description=(
                f"[ShieldOps] {remediation.get('name', remediation.get('action', 'Remediation'))}"
            ),
            description="\n".join(description_parts),
            type=remediation.get("change_type", "normal"),
            risk=risk_map.get(risk_level, "moderate"),
            impact=impact,
            assignment_group=remediation.get("assignment_group"),
        )

    # ------------------------------------------------------------------
    # Webhook handler
    # ------------------------------------------------------------------

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming ServiceNow webhook notification.

        ServiceNow Business Rules can POST JSON payloads to ShieldOps on
        state transitions.  This method normalises the payload into a
        standard event dict.

        Expected webhook payload keys: ``sys_id``, ``number``, ``state``,
        ``table``, ``action`` (insert/update/delete).

        Returns a dict with ``event_type``, ``shieldops_state``, and the
        original record fields.
        """
        table = payload.get("table", "incident")
        action = payload.get("action", "update")
        state_value = payload.get("state")
        sys_id = payload.get("sys_id", "")
        number = payload.get("number", "")

        # Map ServiceNow numeric state to ShieldOps state
        shieldops_state: str | None = None
        if state_value is not None:
            try:
                snow_state = int(state_value)
                shieldops_state = SNOW_TO_SHIELDOPS_STATE.get(snow_state)
            except (ValueError, TypeError):
                logger.warning(
                    "servicenow_webhook_bad_state",
                    state=state_value,
                    sys_id=sys_id,
                )

        event_type = f"servicenow.{table}.{action}"

        logger.info(
            "servicenow_webhook_received",
            event_type=event_type,
            sys_id=sys_id,
            number=number,
            snow_state=state_value,
            shieldops_state=shieldops_state,
        )

        return {
            "event_type": event_type,
            "table": table,
            "action": action,
            "sys_id": sys_id,
            "number": number,
            "state": state_value,
            "shieldops_state": shieldops_state,
            "payload": payload,
        }

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict[str, Any]:
        """Verify connectivity by querying the incident table with limit=1.

        Returns a dict with ``connected`` (bool) and ``instance_url``.
        """
        try:
            await self._request(
                "GET",
                "/api/now/table/incident",
                params={"sysparm_limit": "1"},
            )
            return {
                "connected": True,
                "instance_url": self._instance_url,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except ServiceNowAuthError:
            return {
                "connected": False,
                "error": "Authentication failed",
                "instance_url": self._instance_url,
            }
        except ServiceNowError as exc:
            return {
                "connected": False,
                "error": str(exc),
                "instance_url": self._instance_url,
            }

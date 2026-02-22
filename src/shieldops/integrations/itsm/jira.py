"""Jira Cloud bidirectional sync integration.

Provides a fully async Jira client for:
- Creating issues from ShieldOps incidents
- Syncing status changes in both directions
- Attaching investigation results as comments
- Processing incoming Jira webhooks

Uses Jira Cloud REST API v3 with Basic auth (email + API token).
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger()

# ── Default Mappings ────────────────────────────────────────────────

DEFAULT_STATUS_TO_JIRA: dict[str, str] = {
    "open": "To Do",
    "investigating": "In Progress",
    "resolved": "Done",
    "escalated": "In Review",
}

DEFAULT_STATUS_FROM_JIRA: dict[str, str] = {
    "To Do": "open",
    "In Progress": "investigating",
    "Done": "resolved",
    "In Review": "escalated",
}

DEFAULT_PRIORITY_TO_JIRA: dict[str, str] = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

DEFAULT_ISSUE_TYPE_MAPPING: dict[str, str] = {
    "incident": "Bug",
    "alert": "Bug",
    "security": "Bug",
    "task": "Task",
    "change": "Story",
}

HTTP_TIMEOUT = 30.0


# ── Pydantic Models ─────────────────────────────────────────────────


class JiraConfig(BaseModel):
    """Configuration for a Jira Cloud connection."""

    base_url: str
    email: str
    api_token: str
    project_key: str = "OPS"
    issue_type_mapping: dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_ISSUE_TYPE_MAPPING)
    )
    priority_mapping: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_PRIORITY_TO_JIRA))
    status_to_jira: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_STATUS_TO_JIRA))
    status_from_jira: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_STATUS_FROM_JIRA))
    field_mapping: dict[str, str] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class JiraIssue(BaseModel):
    """Normalized representation of a Jira issue."""

    key: str
    summary: str
    status: str
    priority: str = ""
    assignee: str | None = None
    created: str = ""
    updated: str = ""
    issue_type: str = ""
    labels: list[str] = Field(default_factory=list)
    description: str = ""


class WebhookEventType(StrEnum):
    """Jira webhook event types we handle."""

    ISSUE_UPDATED = "jira:issue_updated"
    ISSUE_CREATED = "jira:issue_created"
    COMMENT_CREATED = "comment_created"
    COMMENT_UPDATED = "comment_updated"


# ── Exceptions ──────────────────────────────────────────────────────


class JiraError(Exception):
    """Base exception for Jira integration errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JiraAuthError(JiraError):
    """Raised when authentication with Jira fails."""


class JiraNotFoundError(JiraError):
    """Raised when the requested Jira resource is not found."""


# ── Client ──────────────────────────────────────────────────────────


class JiraClient:
    """Async client for Jira Cloud REST API v3.

    Uses httpx.AsyncClient for all HTTP operations.  Auth is HTTP Basic
    with email:api_token (base64-encoded), per Jira Cloud requirements.
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: str = "OPS",
        *,
        status_to_jira: dict[str, str] | None = None,
        status_from_jira: dict[str, str] | None = None,
        priority_mapping: dict[str, str] | None = None,
        issue_type_mapping: dict[str, str] | None = None,
        field_mapping: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_key = project_key
        self._email = email
        self._api_token = api_token

        # Build basic-auth header value once
        credentials = f"{email}:{api_token}"
        b64 = base64.b64encode(credentials.encode()).decode()
        self._auth_header = f"Basic {b64}"

        # Configurable mappings
        self.status_to_jira = status_to_jira or dict(DEFAULT_STATUS_TO_JIRA)
        self.status_from_jira = status_from_jira or dict(DEFAULT_STATUS_FROM_JIRA)
        self.priority_mapping = priority_mapping or dict(DEFAULT_PRIORITY_TO_JIRA)
        self.issue_type_mapping = issue_type_mapping or dict(DEFAULT_ISSUE_TYPE_MAPPING)
        self.field_mapping = field_mapping or {}

    # ── HTTP helpers ────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request to the Jira API and return parsed JSON.

        Raises JiraAuthError on 401/403, JiraNotFoundError on 404,
        and JiraError on other non-2xx responses.
        """
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                json=json,
            )

        if response.status_code in (401, 403):
            raise JiraAuthError(
                f"Jira authentication failed: {response.status_code}",
                status_code=response.status_code,
            )
        if response.status_code == 404:
            raise JiraNotFoundError(
                f"Jira resource not found: {path}",
                status_code=404,
            )
        if response.status_code >= 400:
            body = response.text
            raise JiraError(
                f"Jira API error {response.status_code}: {body}",
                status_code=response.status_code,
            )

        # 204 No Content
        if response.status_code == 204:
            return {}

        return dict(response.json())

    # ── Core CRUD ───────────────────────────────────────────────────

    async def create_issue(
        self,
        summary: str,
        description: str,
        issue_type: str = "Bug",
        priority: str = "Medium",
        labels: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new Jira issue.

        Returns the API response dict containing at least ``key``,
        ``id``, and ``self`` URL.
        """
        fields: dict[str, Any] = {
            "project": {"key": self.project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }

        if labels:
            fields["labels"] = labels

        if custom_fields:
            fields.update(custom_fields)

        payload = {"fields": fields}

        logger.info(
            "jira_create_issue",
            project=self.project_key,
            issue_type=issue_type,
            summary=summary[:80],
        )

        result = await self._request("POST", "/rest/api/3/issue", json=payload)
        logger.info("jira_issue_created", key=result.get("key"))
        return result

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch a single Jira issue by key (e.g. ``OPS-123``)."""
        return await self._request("GET", f"/rest/api/3/issue/{issue_key}")

    async def update_issue(
        self,
        issue_key: str,
        *,
        status: str | None = None,
        comment: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing issue's fields and/or transition its status.

        Parameters
        ----------
        issue_key:
            The Jira issue key, e.g. ``OPS-42``.
        status:
            Target status name.  If provided, the method looks up the
            matching transition and executes it.
        comment:
            If provided, a comment is added to the issue.
        fields:
            Arbitrary field updates (merged into the PUT body).
        """
        result: dict[str, Any] = {}

        # 1. Field updates
        if fields:
            await self._request(
                "PUT",
                f"/rest/api/3/issue/{issue_key}",
                json={"fields": fields},
            )
            result["fields_updated"] = True

        # 2. Status transition
        if status:
            transition_id = await self._find_transition(issue_key, status)
            if transition_id:
                await self._request(
                    "POST",
                    f"/rest/api/3/issue/{issue_key}/transitions",
                    json={"transition": {"id": transition_id}},
                )
                result["transitioned_to"] = status
                logger.info(
                    "jira_issue_transitioned",
                    issue=issue_key,
                    status=status,
                )
            else:
                logger.warning(
                    "jira_transition_not_found",
                    issue=issue_key,
                    target_status=status,
                )
                result["transition_error"] = f"No transition found for status '{status}'"

        # 3. Comment
        if comment:
            await self.add_comment(issue_key, comment)
            result["comment_added"] = True

        return result

    async def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        """Add a comment to a Jira issue using ADF (Atlassian Document Format)."""
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            }
        }
        return await self._request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/comment",
            json=payload,
        )

    async def _find_transition(self, issue_key: str, target_status: str) -> str | None:
        """Look up the transition ID that moves an issue to *target_status*.

        Returns ``None`` if no matching transition is available.
        """
        data = await self._request(
            "GET",
            f"/rest/api/3/issue/{issue_key}/transitions",
        )
        for transition in data.get("transitions", []):
            to_status = transition.get("to", {}).get("name", "")
            if to_status.lower() == target_status.lower():
                return str(transition["id"])
        return None

    # ── Incident mapping ────────────────────────────────────────────

    async def create_from_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Map a ShieldOps incident dict to a Jira issue and create it.

        Expected incident keys (all optional with fallbacks):
        - ``title`` / ``alert_name``
        - ``description``
        - ``severity`` (critical / high / medium / low)
        - ``service``
        - ``environment``
        - ``incident_id``
        - ``type`` (incident / alert / security / task)
        """
        title = incident.get("title") or incident.get("alert_name", "ShieldOps Incident")
        severity = incident.get("severity", "medium").lower()
        incident_type = incident.get("type", "incident").lower()
        service = incident.get("service", "")
        environment = incident.get("environment", "production")
        incident_id = incident.get("incident_id", "")

        summary = f"[ShieldOps] {title}"
        if service:
            summary = f"[ShieldOps][{service}] {title}"

        description_parts = [
            f"**Incident ID:** {incident_id}" if incident_id else "",
            f"**Severity:** {severity}",
            f"**Service:** {service}" if service else "",
            f"**Environment:** {environment}",
            "",
            incident.get("description", "No description provided."),
        ]
        description = "\n".join(part for part in description_parts if part or part == "")

        issue_type = self.issue_type_mapping.get(incident_type, "Bug")
        priority = self.priority_mapping.get(severity, "Medium")

        labels = ["shieldops", "auto-created"]
        if environment:
            labels.append(f"env-{environment}")

        custom_fields: dict[str, Any] = {}
        # Apply configured field mappings
        for incident_field, jira_field in self.field_mapping.items():
            value = incident.get(incident_field)
            if value is not None:
                custom_fields[jira_field] = value

        result = await self.create_issue(
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            labels=labels,
            custom_fields=custom_fields if custom_fields else None,
        )

        logger.info(
            "jira_incident_synced",
            incident_id=incident_id,
            jira_key=result.get("key"),
        )
        return result

    # ── Status sync ─────────────────────────────────────────────────

    async def sync_status(self, issue_key: str, shieldops_status: str) -> dict[str, Any]:
        """Translate a ShieldOps status and transition the Jira issue.

        Returns a dict with the transition outcome.
        """
        jira_status = self.status_to_jira.get(shieldops_status.lower())
        if not jira_status:
            logger.warning(
                "jira_status_unmapped",
                shieldops_status=shieldops_status,
            )
            return {"error": f"No Jira mapping for status '{shieldops_status}'"}

        return await self.update_issue(issue_key, status=jira_status)

    # ── Webhook handling ────────────────────────────────────────────

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming Jira webhook payload.

        Handles:
        - ``jira:issue_updated`` -- extracts status changes and maps
          back to ShieldOps statuses
        - ``jira:issue_created`` -- acknowledges new issues
        - ``comment_created`` / ``comment_updated`` -- extracts comment
          body for downstream processing

        Returns a dict describing the event and any mapped values.
        """
        event_type = payload.get("webhookEvent", "")
        issue_data = payload.get("issue", {})
        issue_key = issue_data.get("key", "")

        result: dict[str, Any] = {
            "event_type": event_type,
            "issue_key": issue_key,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if event_type == WebhookEventType.ISSUE_UPDATED:
            result.update(self._handle_issue_updated(payload))
        elif event_type == WebhookEventType.ISSUE_CREATED:
            result["action"] = "issue_created"
            fields = issue_data.get("fields", {})
            result["summary"] = fields.get("summary", "")
            result["status"] = fields.get("status", {}).get("name", "")
        elif event_type in (
            WebhookEventType.COMMENT_CREATED,
            WebhookEventType.COMMENT_UPDATED,
        ):
            result.update(self._handle_comment_event(payload))
        else:
            result["action"] = "unhandled"
            logger.debug("jira_webhook_unhandled", event_type=event_type)

        logger.info(
            "jira_webhook_processed",
            event_type=event_type,
            issue_key=issue_key,
            action=result.get("action"),
        )
        return result

    def _handle_issue_updated(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Extract status change from an issue_updated webhook."""
        changelog = payload.get("changelog", {})
        items = changelog.get("items", [])
        result: dict[str, Any] = {"action": "issue_updated"}

        for item in items:
            if item.get("field") == "status":
                from_status = item.get("fromString", "")
                to_status = item.get("toString", "")
                result["status_change"] = {
                    "from_jira": from_status,
                    "to_jira": to_status,
                }

                # Map Jira status back to ShieldOps
                mapped_status = self.status_from_jira.get(to_status)
                if mapped_status:
                    result["shieldops_status"] = mapped_status
                else:
                    result["shieldops_status"] = None
                    logger.warning(
                        "jira_status_unmapped_from_jira",
                        jira_status=to_status,
                    )
                break  # Only process first status change

        return result

    def _handle_comment_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Extract comment body from a comment webhook."""
        comment = payload.get("comment", {})
        comment_body = ""

        # ADF body -> extract plain text
        body = comment.get("body", {})
        if isinstance(body, dict):
            content_blocks = body.get("content", [])
            text_parts: list[str] = []
            for block in content_blocks:
                for inline in block.get("content", []):
                    if inline.get("type") == "text":
                        text_parts.append(inline.get("text", ""))
            comment_body = " ".join(text_parts)
        elif isinstance(body, str):
            comment_body = body

        return {
            "action": "comment_added",
            "comment_id": comment.get("id", ""),
            "comment_body": comment_body,
            "comment_author": comment.get("author", {}).get("displayName", ""),
        }

    # ── Connection test ─────────────────────────────────────────────

    async def test_connection(self) -> dict[str, Any]:
        """Verify credentials and connectivity by calling /rest/api/3/myself.

        Returns account info on success; raises on failure.
        """
        data = await self._request("GET", "/rest/api/3/myself")
        return {
            "connected": True,
            "account_id": data.get("accountId", ""),
            "display_name": data.get("displayName", ""),
            "email": data.get("emailAddress", ""),
        }

    # ── Helpers ──────────────────────────────────────────────────────

    def parse_issue(self, raw: dict[str, Any]) -> JiraIssue:
        """Parse a raw Jira API issue response into a ``JiraIssue`` model."""
        fields = raw.get("fields", {})
        return JiraIssue(
            key=raw.get("key", ""),
            summary=fields.get("summary", ""),
            status=fields.get("status", {}).get("name", ""),
            priority=fields.get("priority", {}).get("name", ""),
            assignee=(fields.get("assignee") or {}).get("displayName"),
            created=fields.get("created", ""),
            updated=fields.get("updated", ""),
            issue_type=fields.get("issuetype", {}).get("name", ""),
            labels=fields.get("labels", []),
            description=_extract_text_from_adf(fields.get("description")),
        )


def _extract_text_from_adf(adf: dict[str, Any] | None) -> str:
    """Recursively extract plain text from an ADF document."""
    if not adf or not isinstance(adf, dict):
        return ""

    parts: list[str] = []
    for block in adf.get("content", []):
        for inline in block.get("content", []):
            if inline.get("type") == "text":
                parts.append(inline.get("text", ""))
    return " ".join(parts)

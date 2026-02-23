"""Incident communication management for structured updates and notifications.

Manages structured communications during incidents including status updates,
stakeholder notifications, public messaging, and communication plans with
escalation timelines.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class MessageType(enum.StrEnum):
    STATUS_UPDATE = "status_update"
    STAKEHOLDER_NOTIFICATION = "stakeholder_notification"
    PUBLIC_UPDATE = "public_update"
    INTERNAL_NOTE = "internal_note"
    RESOLUTION_NOTICE = "resolution_notice"


class AudienceType(enum.StrEnum):
    ENGINEERING = "engineering"
    MANAGEMENT = "management"
    CUSTOMERS = "customers"
    PUBLIC = "public"
    ALL = "all"


# -- Models --------------------------------------------------------------------


class CommunicationTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    message_type: MessageType
    subject_template: str = ""
    body_template: str = ""
    audience: AudienceType = AudienceType.ENGINEERING
    created_at: float = Field(default_factory=time.time)


class IncidentMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    message_type: MessageType
    audience: AudienceType = AudienceType.ENGINEERING
    subject: str = ""
    body: str = ""
    sent_by: str = ""
    sent_at: float = Field(default_factory=time.time)
    channels: list[str] = Field(default_factory=list)
    acknowledged_by: list[str] = Field(default_factory=list)


class CommunicationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    template_ids: list[str] = Field(default_factory=list)
    escalation_minutes: list[int] = Field(default_factory=lambda: [15, 30, 60])
    auto_notify: bool = True
    created_at: float = Field(default_factory=time.time)


# -- Manager ------------------------------------------------------------------


class IncidentCommunicationManager:
    """Manage structured communications during incidents.

    Parameters
    ----------
    max_templates:
        Maximum number of communication templates to store.
    max_messages:
        Maximum number of incident messages to store.
    """

    def __init__(
        self,
        max_templates: int = 500,
        max_messages: int = 50000,
    ) -> None:
        self._templates: dict[str, CommunicationTemplate] = {}
        self._messages: list[IncidentMessage] = []
        self._plans: dict[str, CommunicationPlan] = {}
        self._max_templates = max_templates
        self._max_messages = max_messages

    def create_template(
        self,
        name: str,
        message_type: MessageType,
        **kw: Any,
    ) -> CommunicationTemplate:
        """Create a new communication template.

        Raises ``ValueError`` if the maximum number of templates has been reached.
        """
        if len(self._templates) >= self._max_templates:
            raise ValueError(f"Maximum templates limit reached: {self._max_templates}")
        template = CommunicationTemplate(name=name, message_type=message_type, **kw)
        self._templates[template.id] = template
        logger.info(
            "communication_template_created",
            template_id=template.id,
            name=name,
            message_type=message_type,
        )
        return template

    def send_message(
        self,
        incident_id: str,
        message_type: MessageType,
        body: str,
        **kw: Any,
    ) -> IncidentMessage:
        """Send (create and store) an incident message.

        Trims stored messages to ``max_messages`` when the limit is exceeded.
        """
        message = IncidentMessage(
            incident_id=incident_id,
            message_type=message_type,
            body=body,
            **kw,
        )
        self._messages.append(message)

        # Trim to max_messages
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages :]

        logger.info(
            "incident_message_sent",
            message_id=message.id,
            incident_id=incident_id,
            message_type=message_type,
        )
        return message

    def acknowledge_message(self, message_id: str, user: str) -> IncidentMessage | None:
        """Acknowledge a message by adding a user to the acknowledged_by list.

        Returns ``None`` if the message is not found.
        """
        for message in self._messages:
            if message.id == message_id:
                if user not in message.acknowledged_by:
                    message.acknowledged_by.append(user)
                logger.info(
                    "incident_message_acknowledged",
                    message_id=message_id,
                    user=user,
                )
                return message
        return None

    def create_plan(
        self,
        incident_id: str,
        template_ids: list[str] | None = None,
        **kw: Any,
    ) -> CommunicationPlan:
        """Create a communication plan for an incident."""
        plan = CommunicationPlan(
            incident_id=incident_id,
            template_ids=template_ids or [],
            **kw,
        )
        self._plans[plan.incident_id] = plan
        logger.info(
            "communication_plan_created",
            plan_id=plan.id,
            incident_id=incident_id,
        )
        return plan

    def get_template(self, template_id: str) -> CommunicationTemplate | None:
        """Return a template by ID, or ``None`` if not found."""
        return self._templates.get(template_id)

    def list_templates(
        self,
        message_type: MessageType | None = None,
    ) -> list[CommunicationTemplate]:
        """List templates with optional message type filter."""
        templates = list(self._templates.values())
        if message_type is not None:
            templates = [t for t in templates if t.message_type == message_type]
        return templates

    def delete_template(self, template_id: str) -> bool:
        """Delete a template. Returns ``True`` if the template existed."""
        return self._templates.pop(template_id, None) is not None

    def get_messages(
        self,
        incident_id: str | None = None,
        message_type: MessageType | None = None,
    ) -> list[IncidentMessage]:
        """Return messages with optional filters."""
        messages = list(self._messages)
        if incident_id is not None:
            messages = [m for m in messages if m.incident_id == incident_id]
        if message_type is not None:
            messages = [m for m in messages if m.message_type == message_type]
        return messages

    def get_plan(self, incident_id: str) -> CommunicationPlan | None:
        """Return the communication plan for an incident, or ``None``."""
        return self._plans.get(incident_id)

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        messages_by_type: dict[str, int] = {}
        messages_by_audience: dict[str, int] = {}
        acknowledged_count = 0

        for message in self._messages:
            type_key = message.message_type.value
            messages_by_type[type_key] = messages_by_type.get(type_key, 0) + 1

            audience_key = message.audience.value
            messages_by_audience[audience_key] = messages_by_audience.get(audience_key, 0) + 1

            if len(message.acknowledged_by) > 0:
                acknowledged_count += 1

        total_messages = len(self._messages)
        acknowledgement_rate = (
            (acknowledged_count / total_messages * 100) if total_messages > 0 else 0.0
        )

        return {
            "total_templates": len(self._templates),
            "total_messages": total_messages,
            "total_plans": len(self._plans),
            "messages_by_type": messages_by_type,
            "messages_by_audience": messages_by_audience,
            "acknowledgement_rate": acknowledgement_rate,
        }

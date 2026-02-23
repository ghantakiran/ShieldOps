"""Incident communications API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/incident-comms", tags=["Incident Communications"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Incident communications service unavailable")
    return _manager


class CreateTemplateRequest(BaseModel):
    name: str
    message_type: str
    subject_template: str = ""
    body_template: str = ""
    audience: str = "engineering"


class SendMessageRequest(BaseModel):
    incident_id: str
    message_type: str
    body: str
    subject: str = ""
    audience: str = "engineering"
    sent_by: str = ""
    channels: list[str] = Field(default_factory=list)


class AcknowledgeRequest(BaseModel):
    user: str


class CreatePlanRequest(BaseModel):
    incident_id: str
    template_ids: list[str] = Field(default_factory=list)
    escalation_minutes: list[int] = Field(default_factory=lambda: [15, 30, 60])
    auto_notify: bool = True


@router.post("/templates")
async def create_template(
    body: CreateTemplateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    template = mgr.create_template(**body.model_dump())
    return template.model_dump()


@router.get("/templates")
async def list_templates(
    message_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [t.model_dump() for t in mgr.list_templates(message_type=message_type)]


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    template = mgr.get_template(template_id)
    if template is None:
        raise HTTPException(404, f"Template '{template_id}' not found")
    return template.model_dump()


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    removed = mgr.delete_template(template_id)
    if not removed:
        raise HTTPException(404, f"Template '{template_id}' not found")
    return {"deleted": True, "template_id": template_id}


@router.post("/messages")
async def send_message(
    body: SendMessageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    message = mgr.send_message(**body.model_dump())
    return message.model_dump()


@router.get("/messages")
async def get_messages(
    incident_id: str | None = None,
    message_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [
        m.model_dump() for m in mgr.get_messages(incident_id=incident_id, message_type=message_type)
    ]


@router.put("/messages/{message_id}/acknowledge")
async def acknowledge_message(
    message_id: str,
    body: AcknowledgeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    message = mgr.acknowledge_message(message_id, body.user)
    if message is None:
        raise HTTPException(404, f"Message '{message_id}' not found")
    return message.model_dump()


@router.post("/plans")
async def create_plan(
    body: CreatePlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    plan = mgr.create_plan(**body.model_dump())
    return plan.model_dump()


@router.get("/plans/{incident_id}")
async def get_plan(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    plan = mgr.get_plan(incident_id)
    if plan is None:
        raise HTTPException(404, f"Plan for incident '{incident_id}' not found")
    return plan.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()

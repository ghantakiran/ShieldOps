"""AI-generated playbook API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/playbooks/ai", tags=["AI Playbooks"])

_generator: Any = None


def set_generator(gen: Any) -> None:
    global _generator
    _generator = gen


class GenerateRequest(BaseModel):
    vulnerability: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)


class BatchGenerateRequest(BaseModel):
    vulnerabilities: list[dict[str, Any]]
    context: dict[str, Any] = Field(default_factory=dict)


class RefineRequest(BaseModel):
    playbook: dict[str, Any]
    feedback: str


@router.post("/generate")
async def generate_playbook(
    body: GenerateRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _generator is None:
        raise HTTPException(status_code=501, detail="AI playbook generation not enabled")

    result = await _generator.generate(body.vulnerability, body.context or None)
    data: dict[str, Any] = result.model_dump()
    return data


@router.post("/generate-batch")
async def generate_batch(
    body: BatchGenerateRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, list[dict[str, Any]]]:
    if _generator is None:
        raise HTTPException(status_code=501, detail="AI playbook generation not enabled")

    results = await _generator.generate_batch(body.vulnerabilities, body.context or None)
    return {"playbooks": [r.model_dump() for r in results]}


@router.post("/refine")
async def refine_playbook(
    body: RefineRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _generator is None:
        raise HTTPException(status_code=501, detail="AI playbook generation not enabled")

    from shieldops.playbooks.ai_generator import GeneratedPlaybook

    playbook = GeneratedPlaybook.model_validate(body.playbook)
    result = await _generator.refine(playbook, body.feedback)
    data: dict[str, Any] = result.model_dump()
    return data

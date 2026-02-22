"""SBOM generation API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/security/sbom", tags=["SBOM"])

_generator: Any = None


def set_generator(gen: Any) -> None:
    global _generator
    _generator = gen


class SBOMGenerateRequest(BaseModel):
    target: str = Field(description="Container image or directory path")
    format: str = Field(default="cyclonedx-json", description="SBOM output format")


class SBOMScanRequest(BaseModel):
    target: str
    severity_threshold: str = "medium"


@router.post("/generate")
async def generate_sbom(
    body: SBOMGenerateRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _generator is None:
        raise HTTPException(status_code=501, detail="SBOM generation not enabled")

    from shieldops.integrations.scanners.sbom_generator import SBOMFormat

    try:
        fmt = SBOMFormat(body.format)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}") from None

    result = await _generator.generate(body.target, fmt)
    data: dict[str, Any] = result.model_dump()
    return data


@router.post("/generate-and-scan")
async def generate_and_scan(
    body: SBOMScanRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _generator is None:
        raise HTTPException(status_code=501, detail="SBOM generation not enabled")

    result: dict[str, Any] = await _generator.generate_and_scan(
        body.target,
        severity_threshold=body.severity_threshold,
    )
    return result


@router.get("/formats")
async def list_formats(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, list[str]]:
    from shieldops.integrations.scanners.sbom_generator import SBOMGenerator

    return {"formats": SBOMGenerator.supported_formats()}

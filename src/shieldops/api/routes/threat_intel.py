"""Threat intelligence API endpoints (MITRE ATT&CK + EPSS)."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/security/threat-intel", tags=["Threat Intel"])

_mitre_mapper: Any = None
_epss_scorer: Any = None


def set_mitre_mapper(mapper: Any) -> None:
    global _mitre_mapper
    _mitre_mapper = mapper


def set_epss_scorer(scorer: Any) -> None:
    global _epss_scorer
    _epss_scorer = scorer


class EnrichRequest(BaseModel):
    cve_id: str
    cwes: list[str] = Field(default_factory=list)
    description: str = ""


class BulkEnrichRequest(BaseModel):
    items: list[EnrichRequest]


@router.get("/cve/{cve_id}/attack-map")
async def get_attack_map(
    cve_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _mitre_mapper is None:
        raise HTTPException(status_code=501, detail="MITRE ATT&CK mapping not enabled")

    result: dict[str, Any] = _mitre_mapper.map_cve({"cve_id": cve_id})
    return result


@router.post("/enrich")
async def enrich_cve(
    body: EnrichRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    result: dict[str, Any] = {"cve_id": body.cve_id}

    if _mitre_mapper:
        attack_map = _mitre_mapper.map_cve(
            {
                "cve_id": body.cve_id,
                "cwes": body.cwes,
                "description": body.description,
            }
        )
        result["attack_map"] = attack_map

    if _epss_scorer:
        epss = await _epss_scorer.score(body.cve_id)
        result["epss"] = epss

    return result


@router.get("/cve/{cve_id}/epss")
async def get_epss_score(
    cve_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _epss_scorer is None:
        raise HTTPException(status_code=501, detail="EPSS scoring not enabled")

    result: dict[str, Any] = await _epss_scorer.score(cve_id)
    return result

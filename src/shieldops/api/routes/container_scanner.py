"""Container image scanner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/container-scanner", tags=["Container Scanner"])

_scanner: Any = None


def set_scanner(scanner: Any) -> None:
    global _scanner
    _scanner = scanner


def _get_scanner() -> Any:
    if _scanner is None:
        raise HTTPException(503, "Container scanner service unavailable")
    return _scanner


class RegisterImageRequest(BaseModel):
    image_name: str
    tag: str = "latest"
    registry: str = ""
    base_image: str = ""
    size_mb: float = 0.0
    layer_count: int = 0


class RecordVulnerabilityRequest(BaseModel):
    image_id: str
    cve_id: str
    severity: str = "LOW"
    package_name: str = ""
    installed_version: str = ""
    fixed_version: str = ""
    fix_status: str = "NO_FIX"


@router.post("/images")
async def register_image(
    body: RegisterImageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    image = scanner.register_image(**body.model_dump())
    return image.model_dump()


@router.get("/images")
async def list_images(
    scan_status: str | None = None,
    risk_level: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    return [
        i.model_dump()
        for i in scanner.list_images(scan_status=scan_status, risk_level=risk_level, limit=limit)
    ]


@router.get("/images/{image_id}")
async def get_image(
    image_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    image = scanner.get_image(image_id)
    if image is None:
        raise HTTPException(404, f"Image '{image_id}' not found")
    return image.model_dump()


@router.post("/vulnerabilities")
async def record_vulnerability(
    body: RecordVulnerabilityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    vuln = scanner.record_vulnerability(**body.model_dump())
    return vuln.model_dump()


@router.post("/scan/{image_id}")
async def scan_image(
    image_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    image = scanner.scan_image(image_id)
    return image.model_dump()


@router.get("/stale")
async def detect_stale_images(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    return [i.model_dump() for i in scanner.detect_stale_images()]


@router.get("/base-image-freshness")
async def analyze_base_image_freshness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    return scanner.analyze_base_image_freshness()


@router.get("/fixable-vulnerabilities")
async def identify_fixable_vulnerabilities(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    return [v.model_dump() for v in scanner.identify_fixable_vulnerabilities()]


@router.get("/report")
async def generate_scan_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    return scanner.generate_scan_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    return scanner.get_stats()

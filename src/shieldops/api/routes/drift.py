"""Terraform Drift Detection API endpoints.

Provides REST endpoints for triggering drift scans, viewing reports,
and listing scan history.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shieldops.agents.security.drift import DriftDetector, DriftScanRequest

logger = structlog.get_logger()

router = APIRouter(prefix="/drift", tags=["Drift Detection"])

# Module-level detector instance, wired at startup via set_detector().
_detector: DriftDetector | None = None


def set_detector(detector: DriftDetector) -> None:
    """Wire the DriftDetector instance into this route module."""
    global _detector
    _detector = detector


def _get_detector() -> DriftDetector:
    if _detector is None:
        raise HTTPException(503, "Drift detection service unavailable")
    return _detector


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class DriftScanAPIRequest(BaseModel):
    """REST request body for POST /drift/scan."""

    tfstate_content: dict[str, Any] | None = None
    tfstate_path: str | None = None
    environment: str = "production"
    providers: list[str] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/scan")
async def start_drift_scan(body: DriftScanAPIRequest) -> dict[str, Any]:
    """Start a drift scan and return the report.

    Accepts either inline tfstate content or a file path.
    """
    detector = _get_detector()

    request = DriftScanRequest(
        tfstate_content=body.tfstate_content,
        tfstate_path=body.tfstate_path,
        environment=body.environment,
        providers=body.providers,
    )

    logger.info(
        "drift_scan_api_request",
        environment=body.environment,
        has_content=body.tfstate_content is not None,
        has_path=body.tfstate_path is not None,
    )

    report = await detector.scan(request)
    return report.model_dump(mode="json")


@router.get("/report")
async def get_latest_report() -> dict[str, Any]:
    """Get the most recent drift report."""
    detector = _get_detector()
    report = detector.get_latest_report()
    if report is None:
        raise HTTPException(404, "No drift reports available")
    return report.model_dump(mode="json")


@router.get("/reports")
async def list_reports() -> dict[str, Any]:
    """List all drift scan reports (newest first)."""
    detector = _get_detector()
    reports = detector.list_reports()
    return {"reports": reports, "total": len(reports)}


@router.get("/report/{scan_id}")
async def get_report_by_id(scan_id: str) -> dict[str, Any]:
    """Get a specific drift report by scan ID."""
    detector = _get_detector()
    report = detector.get_report(scan_id)
    if report is None:
        raise HTTPException(404, f"Drift report '{scan_id}' not found")
    return report.model_dump(mode="json")

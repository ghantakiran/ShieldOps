"""Data export & compliance report endpoints.

Provides CSV and JSON exports for investigations, remediations, and
security compliance data.  All endpoints require at least ``viewer``
role and stream CSV output for efficient handling of large result sets.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserRole
from shieldops.utils.export_helpers import dicts_to_csv

logger = structlog.get_logger()
router = APIRouter(prefix="/export", tags=["Export"])

_repository: Any | None = None

# Fields to include in each CSV export (order matters for readability)
_INVESTIGATION_CSV_FIELDS: list[str] = [
    "investigation_id",
    "alert_id",
    "alert_name",
    "severity",
    "status",
    "confidence",
    "hypotheses_count",
    "duration_ms",
    "error",
    "created_at",
    "updated_at",
]

_REMEDIATION_CSV_FIELDS: list[str] = [
    "remediation_id",
    "action_type",
    "target_resource",
    "environment",
    "risk_level",
    "status",
    "validation_passed",
    "investigation_id",
    "duration_ms",
    "error",
    "created_at",
    "updated_at",
]

_COMPLIANCE_CSV_FIELDS: list[str] = [
    "scan_id",
    "scan_type",
    "environment",
    "status",
    "compliance_score",
    "critical_cve_count",
    "patches_applied",
    "credentials_rotated",
    "duration_ms",
    "error",
    "created_at",
    "updated_at",
]


class ExportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"


def set_repository(repo: Any) -> None:
    """Set the repository instance for export route handlers."""
    global _repository
    _repository = repo


def _get_repo(request: Request) -> Any:
    """Resolve repository from module state or app.state."""
    repo = _repository or getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DB unavailable",
        )
    return repo


def _clamp_limit(limit: int) -> int:
    """Clamp the export limit to the allowed maximum of 10000."""
    return max(1, min(limit, 10_000))


def _csv_streaming_response(
    csv_body: str,
    filename: str,
) -> StreamingResponse:
    """Wrap a CSV string in a StreamingResponse with proper headers."""
    return StreamingResponse(
        iter([csv_body]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ── Investigations export ────────────────────────────────────────────


@router.get("/investigations")
async def export_investigations(
    request: Request,
    format: ExportFormat = Query(ExportFormat.CSV),
    start_date: str | None = Query(None, description="ISO date"),
    end_date: str | None = Query(None, description="ISO date"),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(1000, ge=1, le=10_000),
    _user: Any = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> Any:
    """Export investigations as CSV or JSON."""
    repo = _get_repo(request)
    limit = _clamp_limit(limit)
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date)

    rows = await repo.export_investigations(
        start_date=parsed_start,
        end_date=parsed_end,
        status=status,
        severity=severity,
        limit=limit,
    )

    if format == ExportFormat.JSON:
        return rows

    csv_body = dicts_to_csv(rows, fieldnames=_INVESTIGATION_CSV_FIELDS)
    return _csv_streaming_response(csv_body, "investigations_export.csv")


# ── Remediations export ──────────────────────────────────────────────


@router.get("/remediations")
async def export_remediations(
    request: Request,
    format: ExportFormat = Query(ExportFormat.CSV),
    start_date: str | None = Query(None, description="ISO date"),
    end_date: str | None = Query(None, description="ISO date"),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(1000, ge=1, le=10_000),
    _user: Any = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> Any:
    """Export remediations as CSV or JSON."""
    repo = _get_repo(request)
    limit = _clamp_limit(limit)
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date)

    rows = await repo.export_remediations(
        start_date=parsed_start,
        end_date=parsed_end,
        status=status,
        severity=severity,
        limit=limit,
    )

    if format == ExportFormat.JSON:
        return rows

    csv_body = dicts_to_csv(rows, fieldnames=_REMEDIATION_CSV_FIELDS)
    return _csv_streaming_response(csv_body, "remediations_export.csv")


# ── Compliance report export ─────────────────────────────────────────


@router.get("/compliance")
async def export_compliance(
    request: Request,
    format: ExportFormat = Query(ExportFormat.CSV),
    start_date: str | None = Query(None, description="ISO date"),
    end_date: str | None = Query(None, description="ISO date"),
    limit: int = Query(1000, ge=1, le=10_000),
    _user: Any = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> Any:
    """Export compliance report (security scan results + posture)."""
    repo = _get_repo(request)
    limit = _clamp_limit(limit)
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date)

    rows = await repo.export_compliance_data(
        start_date=parsed_start,
        end_date=parsed_end,
        limit=limit,
    )

    if format == ExportFormat.JSON:
        return rows

    csv_body = dicts_to_csv(rows, fieldnames=_COMPLIANCE_CSV_FIELDS)
    return _csv_streaming_response(csv_body, "compliance_export.csv")


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_date(value: str | None) -> datetime | None:
    """Parse an ISO-format date string into a datetime, or return None."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date format: {value!r}. Use ISO 8601.",
        ) from exc

"""Backup verification API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/backup-verification",
    tags=["Backup Verification"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Backup verification service unavailable")
    return _engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterBackupRequest(BaseModel):
    service: str
    backup_type: str = "full"
    size_bytes: int = 0
    location: str = ""
    checksum: str = ""


class VerifyBackupRequest(BaseModel):
    integrity_check: bool = True
    restore_test: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/backups")
async def register_backup(
    body: RegisterBackupRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.register_backup(
        service=body.service,
        backup_type=body.backup_type,
        size_bytes=body.size_bytes,
        location=body.location,
        checksum=body.checksum,
    )
    return record.model_dump()


@router.get("/backups")
async def list_backups(
    service: str | None = None,
    backup_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    backups = engine.list_backups(service=service, backup_type=backup_type, status=status)
    return [b.model_dump() for b in backups[-limit:]]


@router.get("/backups/{backup_id}")
async def get_backup(
    backup_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    backup = engine.get_backup(backup_id)
    if backup is None:
        raise HTTPException(404, f"Backup '{backup_id}' not found")
    return backup.model_dump()


@router.post("/backups/{backup_id}/verify")
async def verify_backup(
    backup_id: str,
    body: VerifyBackupRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.verify_backup(
        backup_id,
        integrity_check=body.integrity_check,
        restore_test=body.restore_test,
    )
    if result is None:
        raise HTTPException(404, f"Backup '{backup_id}' not found")
    return result.model_dump()


@router.get("/stale")
async def get_stale_backups(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    stale = engine.get_stale_backups()
    return [b.model_dump() for b in stale]


@router.get("/recovery/{service}")
async def get_recovery_report(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_recovery_report(service).model_dump()


@router.get("/recovery-readiness")
async def get_recovery_readiness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    reports = engine.get_recovery_readiness_all()
    return [r.model_dump() for r in reports]


@router.get("/verifications")
async def list_verifications(
    backup_id: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    verifications = engine.list_verifications(backup_id=backup_id, limit=limit)
    return [v.model_dump() for v in verifications]


@router.delete("/backups/{backup_id}")
async def delete_backup(
    backup_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    deleted = engine.delete_backup(backup_id)
    if not deleted:
        raise HTTPException(404, f"Backup '{backup_id}' not found")
    return {"deleted": True, "backup_id": backup_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()

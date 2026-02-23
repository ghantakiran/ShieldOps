"""GDPR data subject request API routes."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from shieldops.compliance.gdpr import DataSubjectRequest, DSRType, GDPRProcessor

logger = structlog.get_logger()
router = APIRouter(prefix="/gdpr", tags=["GDPR"])

_processor: GDPRProcessor | None = None


def set_processor(processor: GDPRProcessor) -> None:
    global _processor
    _processor = processor


def _get_processor() -> GDPRProcessor:
    if _processor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GDPR processor not initialized",
        )
    return _processor


class CreateDSRRequest(BaseModel):
    subject_id: str
    request_type: DSRType
    reason: str = ""


@router.post("/requests")
async def create_dsr(request: CreateDSRRequest) -> dict[str, Any]:
    """Create a data subject request."""
    processor = _get_processor()
    dsr = DataSubjectRequest(
        subject_id=request.subject_id,
        request_type=request.request_type,
        reason=request.reason,
    )
    created = processor.create_request(dsr)

    # Auto-process the request
    result = await processor.process_request(created.id)
    if result:
        return result.model_dump()
    return created.model_dump()


@router.get("/requests")
async def list_dsrs(
    request_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List data subject requests."""
    processor = _get_processor()
    requests = processor.list_requests(status=request_status, limit=limit)
    return {
        "items": [r.model_dump() for r in requests],
        "total": len(requests),
    }


@router.get("/requests/{request_id}")
async def get_dsr(request_id: str) -> dict[str, Any]:
    """Get DSR status and result."""
    processor = _get_processor()
    dsr = processor.get_request(request_id)
    if dsr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DSR '{request_id}' not found",
        )
    return dsr.model_dump()


@router.get("/dpa-report")
async def get_dpa_report() -> dict[str, Any]:
    """Generate a Data Processing Activities report."""
    processor = _get_processor()
    report = processor.generate_dpa_report()
    return report.model_dump()

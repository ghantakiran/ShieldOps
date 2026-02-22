"""API routes for PCI-DSS and HIPAA compliance reports."""

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shieldops.compliance.evidence_exporter import EvidenceExporter
from shieldops.compliance.hipaa import HIPAAEngine
from shieldops.compliance.pci_dss import PCIDSSEngine

router = APIRouter()

_pci_engine: PCIDSSEngine | None = None
_hipaa_engine: HIPAAEngine | None = None
_exporter: EvidenceExporter | None = None


def set_pci_engine(engine: PCIDSSEngine) -> None:
    global _pci_engine
    _pci_engine = engine


def set_hipaa_engine(engine: HIPAAEngine) -> None:
    global _hipaa_engine
    _hipaa_engine = engine


def set_exporter(exporter: EvidenceExporter) -> None:
    global _exporter
    _exporter = exporter


@router.get("/compliance/pci-dss/report")
async def pci_dss_report() -> dict[str, Any]:
    if _pci_engine is None:
        raise HTTPException(status_code=503, detail="PCI-DSS engine not initialized")
    report = await _pci_engine.evaluate()
    return report.model_dump()


@router.get("/compliance/hipaa/report")
async def hipaa_report() -> dict[str, Any]:
    if _hipaa_engine is None:
        raise HTTPException(status_code=503, detail="HIPAA engine not initialized")
    report = await _hipaa_engine.evaluate()
    return report.model_dump()


@router.post("/compliance/export")
async def export_evidence(framework: str = "soc2") -> StreamingResponse:
    if _exporter is None:
        raise HTTPException(status_code=503, detail="Evidence exporter not initialized")

    controls: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    if framework == "pci-dss" and _pci_engine:
        pci_report = await _pci_engine.evaluate()
        controls = [c.model_dump() for c in pci_report.controls]
        summary = {"score": pci_report.overall_score, "framework": "pci-dss"}
    elif framework == "hipaa" and _hipaa_engine:
        hipaa_report = await _hipaa_engine.evaluate()
        controls = [c.model_dump() for c in hipaa_report.controls]
        summary = {"score": hipaa_report.overall_score, "framework": "hipaa"}
    else:
        controls = []
        summary = {"framework": framework}

    buffer, package = _exporter.export_evidence(framework, controls, summary)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={framework}-evidence-{package.id}.zip"
        },
    )

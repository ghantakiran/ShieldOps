"""Evidence exporter — generates audit evidence packages for compliance reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4
from zipfile import ZipFile

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class EvidencePackage(BaseModel):
    """Metadata about an exported evidence package."""

    id: str = Field(default_factory=lambda: f"evid-{uuid4().hex[:12]}")
    framework: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_controls: int = 0
    total_evidence_items: int = 0
    file_size_bytes: int = 0


class EvidenceExporter:
    """Generates ZIP evidence packages for compliance audits."""

    def export_evidence(
        self,
        framework: str,
        controls: list[dict[str, Any]],
        report_summary: dict[str, Any] | None = None,
    ) -> tuple[BytesIO, EvidencePackage]:
        """Export compliance evidence as a ZIP archive.

        Args:
            framework: Compliance framework name (soc2, pci-dss, hipaa).
            controls: List of control dicts with evidence.
            report_summary: Optional summary data to include.

        Returns:
            Tuple of (ZIP file buffer, package metadata).
        """
        buffer = BytesIO()
        total_evidence = 0

        with ZipFile(buffer, "w") as zf:
            # Write report summary
            if report_summary:
                zf.writestr(
                    f"{framework}/summary.json",
                    json.dumps(report_summary, indent=2, default=str),
                )

            # Write each control's evidence
            for control in controls:
                ctrl_id = control.get("id", "unknown")
                evidence = control.get("evidence", [])
                total_evidence += len(evidence)

                # Control metadata
                ctrl_data = {
                    "id": ctrl_id,
                    "name": control.get("name", ""),
                    "status": control.get("status", ""),
                    "details": control.get("details", ""),
                    "last_checked": str(control.get("last_checked", "")),
                }
                zf.writestr(
                    f"{framework}/controls/{ctrl_id}/control.json",
                    json.dumps(ctrl_data, indent=2, default=str),
                )

                # Evidence items
                for i, ev_item in enumerate(evidence):
                    zf.writestr(
                        f"{framework}/controls/{ctrl_id}/evidence_{i + 1}.json",
                        json.dumps(ev_item, indent=2, default=str),
                    )

            # Write manifest
            manifest = {
                "framework": framework,
                "generated_at": datetime.now(UTC).isoformat(),
                "total_controls": len(controls),
                "total_evidence_items": total_evidence,
            }
            zf.writestr(
                f"{framework}/manifest.json",
                json.dumps(manifest, indent=2, default=str),
            )

        buffer.seek(0)
        file_size = buffer.getbuffer().nbytes

        package = EvidencePackage(
            framework=framework,
            total_controls=len(controls),
            total_evidence_items=total_evidence,
            file_size_bytes=file_size,
        )

        logger.info(
            "evidence_exported",
            framework=framework,
            controls=len(controls),
            evidence_items=total_evidence,
            size_bytes=file_size,
        )

        return buffer, package

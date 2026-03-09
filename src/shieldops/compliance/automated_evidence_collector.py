"""Automated Evidence Collector — automatically collect compliance evidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceType(StrEnum):
    LOG = "log"
    SCREENSHOT = "screenshot"
    CONFIG_SNAPSHOT = "config_snapshot"
    SCAN_REPORT = "scan_report"
    AUDIT_TRAIL = "audit_trail"
    POLICY_DOCUMENT = "policy_document"


class CollectionStatus(StrEnum):
    PENDING = "pending"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    VALIDATED = "validated"
    EXPIRED = "expired"
    FAILED = "failed"


class ControlFramework(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    ISO27001 = "iso27001"
    NIST = "nist"


# --- Models ---


class EvidenceRequirement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    framework: ControlFramework = ControlFramework.SOC2
    evidence_type: EvidenceType = EvidenceType.LOG
    description: str = ""
    required: bool = True
    created_at: float = Field(default_factory=time.time)


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement_id: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG
    status: CollectionStatus = CollectionStatus.PENDING
    content_hash: str = ""
    valid: bool = False
    source: str = ""
    team: str = ""
    expires_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class EvidenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_requirements: int = 0
    total_items: int = 0
    collection_rate: float = 0.0
    validation_rate: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedEvidenceCollector:
    """Automatically collect compliance evidence."""

    def __init__(
        self,
        max_records: int = 200000,
    ) -> None:
        self._max_records = max_records
        self._requirements: list[EvidenceRequirement] = []
        self._items: list[EvidenceItem] = []
        logger.info(
            "automated_evidence_collector.initialized",
            max_records=max_records,
        )

    def identify_evidence_requirements(
        self,
        control_id: str,
        framework: ControlFramework = ControlFramework.SOC2,
        evidence_type: EvidenceType = EvidenceType.LOG,
        description: str = "",
        required: bool = True,
    ) -> EvidenceRequirement:
        """Identify and register an evidence requirement."""
        req = EvidenceRequirement(
            control_id=control_id,
            framework=framework,
            evidence_type=evidence_type,
            description=description,
            required=required,
        )
        self._requirements.append(req)
        if len(self._requirements) > self._max_records:
            self._requirements = self._requirements[-self._max_records :]
        logger.info(
            "automated_evidence_collector.requirement_identified",
            requirement_id=req.id,
            control_id=control_id,
            framework=framework.value,
        )
        return req

    def collect_evidence(
        self,
        requirement_id: str,
        evidence_type: EvidenceType = EvidenceType.LOG,
        content_hash: str = "",
        source: str = "",
        team: str = "",
        expires_at: float = 0.0,
    ) -> EvidenceItem:
        """Collect evidence for a requirement."""
        item = EvidenceItem(
            requirement_id=requirement_id,
            evidence_type=evidence_type,
            status=CollectionStatus.COLLECTED,
            content_hash=content_hash,
            source=source,
            team=team,
            expires_at=expires_at,
        )
        self._items.append(item)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "automated_evidence_collector.evidence_collected",
            item_id=item.id,
            requirement_id=requirement_id,
        )
        return item

    def validate_evidence(self, item_id: str) -> dict[str, Any]:
        """Validate a collected evidence item."""
        for item in self._items:
            if item.id == item_id:
                if item.content_hash and item.status == CollectionStatus.COLLECTED:
                    item.valid = True
                    item.status = CollectionStatus.VALIDATED
                    return {"item_id": item_id, "valid": True, "status": "validated"}
                return {
                    "item_id": item_id,
                    "valid": False,
                    "reason": "missing_hash_or_not_collected",
                }
        return {"item_id": item_id, "valid": False, "reason": "not_found"}

    def store_evidence(self, item_id: str, content_hash: str) -> dict[str, Any]:
        """Store evidence with integrity hash."""
        for item in self._items:
            if item.id == item_id:
                item.content_hash = content_hash
                return {"item_id": item_id, "stored": True, "hash": content_hash}
        return {"item_id": item_id, "stored": False, "reason": "not_found"}

    def get_evidence_status(self) -> dict[str, Any]:
        """Get overall evidence collection status."""
        if not self._requirements:
            return {"total_requirements": 0, "collection_rate": 0.0, "validation_rate": 0.0}
        req_ids = {r.id for r in self._requirements}
        collected_reqs = {
            i.requirement_id
            for i in self._items
            if i.status in (CollectionStatus.COLLECTED, CollectionStatus.VALIDATED)
        }
        covered = len(req_ids & collected_reqs)
        validated = sum(1 for i in self._items if i.status == CollectionStatus.VALIDATED)
        total_items = len(self._items) if self._items else 1
        return {
            "total_requirements": len(self._requirements),
            "total_items": len(self._items),
            "collection_rate": round(covered / len(self._requirements) * 100, 2),
            "validation_rate": round(validated / total_items * 100, 2),
        }

    def list_requirements(
        self,
        framework: ControlFramework | None = None,
        evidence_type: EvidenceType | None = None,
        limit: int = 50,
    ) -> list[EvidenceRequirement]:
        """List requirements with optional filters."""
        results = list(self._requirements)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if evidence_type is not None:
            results = [r for r in results if r.evidence_type == evidence_type]
        return results[-limit:]

    def generate_report(self) -> EvidenceReport:
        """Generate a comprehensive evidence report."""
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for i in self._items:
            by_type[i.evidence_type.value] = by_type.get(i.evidence_type.value, 0) + 1
            by_status[i.status.value] = by_status.get(i.status.value, 0) + 1
        by_fw: dict[str, int] = {}
        for r in self._requirements:
            by_fw[r.framework.value] = by_fw.get(r.framework.value, 0) + 1
        status = self.get_evidence_status()
        col_rate = status.get("collection_rate", 0.0)
        val_rate = status.get("validation_rate", 0.0)
        uncovered = [
            r.control_id
            for r in self._requirements
            if r.id not in {i.requirement_id for i in self._items}
        ][:5]
        recs: list[str] = []
        if uncovered:
            recs.append(f"{len(uncovered)} requirement(s) without evidence")
        if col_rate < 80:
            recs.append(f"Collection rate {col_rate}% needs improvement")
        if not recs:
            recs.append("Evidence collection within healthy range")
        return EvidenceReport(
            total_requirements=len(self._requirements),
            total_items=len(self._items),
            collection_rate=col_rate,
            validation_rate=val_rate,
            by_type=by_type,
            by_status=by_status,
            by_framework=by_fw,
            top_gaps=uncovered,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for r in self._requirements:
            key = r.framework.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_requirements": len(self._requirements),
            "total_items": len(self._items),
            "framework_distribution": dist,
            "unique_sources": len({i.source for i in self._items}),
            "unique_teams": len({i.team for i in self._items}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._requirements.clear()
        self._items.clear()
        logger.info("automated_evidence_collector.cleared")
        return {"status": "cleared"}

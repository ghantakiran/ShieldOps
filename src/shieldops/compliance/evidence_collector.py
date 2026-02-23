"""Compliance Evidence Collector — collects and organizes evidence for audits."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvidenceType(StrEnum):
    SCREENSHOT = "screenshot"
    LOG_EXPORT = "log_export"
    CONFIGURATION = "configuration"
    POLICY_DOCUMENT = "policy_document"
    TEST_RESULT = "test_result"
    APPROVAL_RECORD = "approval_record"


class FrameworkType(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    NIST = "nist"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    evidence_type: EvidenceType
    framework: FrameworkType
    control_id: str = Field(default="")
    description: str = Field(default="")
    source_system: str = Field(default="")
    file_path: str = Field(default="")
    hash_value: str = Field(default="")
    collected_by: str = Field(default="")
    valid_from: float | None = Field(default=None)
    valid_until: float | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
    collected_at: float = Field(default_factory=time.time)


class AuditPackage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    framework: FrameworkType
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="draft")
    reviewer: str = Field(default="")
    review_notes: str = Field(default="")
    created_at: float = Field(default_factory=time.time)
    finalized_at: float | None = Field(default=None)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ComplianceEvidenceCollector:
    """Collects and organizes compliance evidence for audits."""

    def __init__(
        self,
        max_evidence: int = 50000,
        max_packages: int = 500,
    ) -> None:
        self.max_evidence = max_evidence
        self.max_packages = max_packages
        self._evidence: dict[str, EvidenceItem] = {}
        self._packages: dict[str, AuditPackage] = {}
        logger.info(
            "compliance_evidence_collector.initialized",
            max_evidence=max_evidence,
            max_packages=max_packages,
        )

    # -- Evidence operations -------------------------------------------------

    def collect_evidence(
        self,
        title: str,
        evidence_type: EvidenceType,
        framework: FrameworkType,
        **kw: Any,
    ) -> EvidenceItem:
        """Collect a piece of compliance evidence."""
        if len(self._evidence) >= self.max_evidence:
            raise ValueError(f"Maximum evidence items ({self.max_evidence}) exceeded")
        item = EvidenceItem(
            title=title,
            evidence_type=evidence_type,
            framework=framework,
            **kw,
        )
        self._evidence[item.id] = item
        logger.info(
            "evidence_collector.evidence_collected",
            evidence_id=item.id,
            title=title,
            framework=framework,
        )
        return item

    def get_evidence(self, evidence_id: str) -> EvidenceItem | None:
        """Return an evidence item by ID."""
        return self._evidence.get(evidence_id)

    def list_evidence(
        self,
        framework: FrameworkType | None = None,
        evidence_type: EvidenceType | None = None,
        control_id: str | None = None,
    ) -> list[EvidenceItem]:
        """List evidence items, optionally filtered."""
        result = list(self._evidence.values())
        if framework is not None:
            result = [e for e in result if e.framework == framework]
        if evidence_type is not None:
            result = [e for e in result if e.evidence_type == evidence_type]
        if control_id is not None:
            result = [e for e in result if e.control_id == control_id]
        return result

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete an evidence item. Returns True if found and deleted."""
        if evidence_id in self._evidence:
            del self._evidence[evidence_id]
            logger.info(
                "evidence_collector.evidence_deleted",
                evidence_id=evidence_id,
            )
            return True
        return False

    # -- Package operations --------------------------------------------------

    def create_package(
        self,
        name: str,
        framework: FrameworkType,
        evidence_ids: list[str] | None = None,
    ) -> AuditPackage:
        """Create an audit package."""
        if len(self._packages) >= self.max_packages:
            raise ValueError(f"Maximum packages ({self.max_packages}) exceeded")
        package = AuditPackage(
            name=name,
            framework=framework,
            evidence_ids=evidence_ids or [],
        )
        self._packages[package.id] = package
        logger.info(
            "evidence_collector.package_created",
            package_id=package.id,
            name=name,
            framework=framework,
        )
        return package

    def add_to_package(self, package_id: str, evidence_id: str) -> AuditPackage | None:
        """Add an evidence item to an audit package."""
        package = self._packages.get(package_id)
        if package is None:
            return None
        if evidence_id not in package.evidence_ids:
            package.evidence_ids.append(evidence_id)
        logger.info(
            "evidence_collector.evidence_added_to_package",
            package_id=package_id,
            evidence_id=evidence_id,
        )
        return package

    def finalize_package(
        self,
        package_id: str,
        reviewer: str,
        notes: str = "",
    ) -> AuditPackage | None:
        """Finalize an audit package with reviewer details."""
        package = self._packages.get(package_id)
        if package is None:
            return None
        package.status = "finalized"
        package.reviewer = reviewer
        package.review_notes = notes
        package.finalized_at = time.time()
        logger.info(
            "evidence_collector.package_finalized",
            package_id=package_id,
            reviewer=reviewer,
        )
        return package

    def get_package(self, package_id: str) -> AuditPackage | None:
        """Return an audit package by ID."""
        return self._packages.get(package_id)

    def list_packages(
        self,
        framework: FrameworkType | None = None,
        status: str | None = None,
    ) -> list[AuditPackage]:
        """List audit packages, optionally filtered."""
        result = list(self._packages.values())
        if framework is not None:
            result = [p for p in result if p.framework == framework]
        if status is not None:
            result = [p for p in result if p.status == status]
        return result

    # -- Coverage & stats ----------------------------------------------------

    def get_coverage(self, framework: FrameworkType) -> dict[str, Any]:
        """Compute evidence coverage for a framework."""
        fw_evidence = [e for e in self._evidence.values() if e.framework == framework]
        all_control_ids = {e.control_id for e in fw_evidence if e.control_id}
        covered_control_ids = {e.control_id for e in fw_evidence if e.control_id}
        # All controls we know about are covered (they have evidence)
        # Total controls = distinct control_ids in evidence
        total = len(all_control_ids)
        covered = len(covered_control_ids)
        coverage_pct = round((covered / total) * 100, 2) if total > 0 else 0.0

        return {
            "total_controls": total,
            "covered_controls": covered,
            "coverage_pct": coverage_pct,
            "uncovered_controls": [],
        }

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        evidence_list = list(self._evidence.values())
        packages_list = list(self._packages.values())

        framework_dist: dict[str, int] = {}
        for e in evidence_list:
            framework_dist[e.framework] = framework_dist.get(e.framework, 0) + 1

        type_dist: dict[str, int] = {}
        for e in evidence_list:
            type_dist[e.evidence_type] = type_dist.get(e.evidence_type, 0) + 1

        finalized = sum(1 for p in packages_list if p.status == "finalized")

        # Coverage per framework
        coverage_by_fw: dict[str, dict[str, Any]] = {}
        for fw in FrameworkType:
            fw_evidence = [e for e in evidence_list if e.framework == fw]
            if fw_evidence:
                coverage_by_fw[fw.value] = self.get_coverage(fw)

        return {
            "total_evidence": len(evidence_list),
            "total_packages": len(packages_list),
            "finalized_packages": finalized,
            "framework_distribution": framework_dist,
            "evidence_type_distribution": type_dist,
            "coverage_by_framework": coverage_by_fw,
        }

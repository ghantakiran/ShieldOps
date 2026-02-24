"""Compliance Evidence Chain — tamper-evident evidence chains."""

from __future__ import annotations

import hashlib
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
    APPROVAL_RECORD = "approval_record"
    SCAN_RESULT = "scan_result"


class ChainStatus(StrEnum):
    VALID = "valid"
    BROKEN = "broken"
    PENDING_VERIFICATION = "pending_verification"
    TAMPERED = "tampered"
    EXPIRED = "expired"


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"


# --- Models ---


class EvidenceItem(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    chain_id: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG
    framework: ComplianceFramework = ComplianceFramework.SOC2
    description: str = ""
    content_hash: str = ""
    previous_hash: str = ""
    sequence_number: int = 0
    collector: str = ""
    verified: bool = False
    created_at: float = Field(default_factory=time.time)


class EvidenceChain(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    framework: ComplianceFramework = ComplianceFramework.SOC2
    status: ChainStatus = ChainStatus.PENDING_VERIFICATION
    item_count: int = 0
    first_item_at: float = 0.0
    last_item_at: float = 0.0
    is_intact: bool = True
    created_at: float = Field(default_factory=time.time)


class EvidenceReport(BaseModel):
    total_chains: int = 0
    total_items: int = 0
    intact_chains: int = 0
    broken_chains: int = 0
    by_framework: dict[str, int] = Field(
        default_factory=dict,
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_status: dict[str, int] = Field(
        default_factory=dict,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Chain Manager ---


class ComplianceEvidenceChain:
    """Maintain tamper-evident compliance evidence chains."""

    def __init__(
        self,
        max_chains: int = 50000,
        max_items_per_chain: int = 10000,
    ) -> None:
        self._max_chains = max_chains
        self._max_items_per_chain = max_items_per_chain
        self._items: list[EvidenceChain] = []
        self._evidence: dict[str, list[EvidenceItem]] = {}
        logger.info(
            "evidence_chain.initialized",
            max_chains=max_chains,
            max_items_per_chain=max_items_per_chain,
        )

    # -- create / get / list --

    def create_chain(
        self,
        framework: ComplianceFramework = (ComplianceFramework.SOC2),
        **kw: Any,
    ) -> EvidenceChain:
        """Create a new evidence chain."""
        chain = EvidenceChain(framework=framework, **kw)
        self._items.append(chain)
        self._evidence[chain.id] = []
        if len(self._items) > self._max_chains:
            removed = self._items.pop(0)
            self._evidence.pop(removed.id, None)
        logger.info(
            "evidence_chain.created",
            chain_id=chain.id,
            framework=framework,
        )
        return chain

    def get_chain(
        self,
        chain_id: str,
    ) -> EvidenceChain | None:
        """Get a single chain by ID."""
        for item in self._items:
            if item.id == chain_id:
                return item
        return None

    def list_chains(
        self,
        framework: ComplianceFramework | None = None,
        status: ChainStatus | None = None,
        limit: int = 50,
    ) -> list[EvidenceChain]:
        """List chains with optional filters."""
        results = list(self._items)
        if framework is not None:
            results = [c for c in results if c.framework == framework]
        if status is not None:
            results = [c for c in results if c.status == status]
        return results[-limit:]

    # -- evidence operations --

    def add_evidence(
        self,
        chain_id: str,
        evidence_type: EvidenceType,
        description: str,
        content_hash: str,
        collector: str = "",
    ) -> EvidenceItem | None:
        """Add evidence to a chain."""
        chain = self.get_chain(chain_id)
        if chain is None:
            return None
        items = self._evidence.get(chain_id, [])
        previous_hash = ""
        seq = 0
        if items:
            last = items[-1]
            previous_hash = self._compute_link_hash(
                last.content_hash,
                last.id,
            )
            seq = last.sequence_number + 1
        item = EvidenceItem(
            chain_id=chain_id,
            evidence_type=evidence_type,
            framework=chain.framework,
            description=description,
            content_hash=content_hash,
            previous_hash=previous_hash,
            sequence_number=seq,
            collector=collector,
            verified=True,
        )
        items.append(item)
        if len(items) > self._max_items_per_chain:
            items = items[-self._max_items_per_chain :]
        self._evidence[chain_id] = items
        # Update chain metadata
        chain.item_count = len(items)
        chain.last_item_at = item.created_at
        if chain.item_count == 1:
            chain.first_item_at = item.created_at
        chain.status = ChainStatus.VALID
        logger.info(
            "evidence_chain.evidence_added",
            chain_id=chain_id,
            item_id=item.id,
            seq=seq,
        )
        return item

    def verify_chain_integrity(
        self,
        chain_id: str,
    ) -> dict[str, Any]:
        """Verify the integrity of a chain."""
        chain = self.get_chain(chain_id)
        if chain is None:
            return {
                "chain_id": chain_id,
                "valid": False,
                "error": "chain not found",
            }
        items = self._evidence.get(chain_id, [])
        if not items:
            return {
                "chain_id": chain_id,
                "valid": True,
                "item_count": 0,
            }
        is_valid = True
        broken_at = -1
        for i in range(1, len(items)):
            prev = items[i - 1]
            expected = self._compute_link_hash(
                prev.content_hash,
                prev.id,
            )
            if items[i].previous_hash != expected:
                is_valid = False
                broken_at = i
                break
        chain.is_intact = is_valid
        if is_valid:
            chain.status = ChainStatus.VALID
        else:
            chain.status = ChainStatus.BROKEN
        logger.info(
            "evidence_chain.verified",
            chain_id=chain_id,
            valid=is_valid,
        )
        return {
            "chain_id": chain_id,
            "valid": is_valid,
            "item_count": len(items),
            "broken_at": broken_at if not is_valid else -1,
        }

    def detect_broken_chains(
        self,
    ) -> list[dict[str, Any]]:
        """Detect chains with integrity issues."""
        broken: list[dict[str, Any]] = []
        for chain in self._items:
            result = self.verify_chain_integrity(chain.id)
            if not result["valid"]:
                broken.append(result)
        return broken

    def calculate_coverage(
        self,
        framework: ComplianceFramework,
    ) -> dict[str, Any]:
        """Calculate evidence coverage for a framework."""
        chains = [c for c in self._items if c.framework == framework]
        total_chains = len(chains)
        total_items = sum(c.item_count for c in chains)
        intact = sum(1 for c in chains if c.is_intact)
        type_dist: dict[str, int] = {}
        for c in chains:
            for item in self._evidence.get(c.id, []):
                key = item.evidence_type.value
                type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "framework": framework.value,
            "total_chains": total_chains,
            "total_items": total_items,
            "intact_chains": intact,
            "coverage_pct": (round(intact / total_chains * 100, 2) if total_chains else 0.0),
            "type_distribution": type_dist,
        }

    def export_chain(
        self,
        chain_id: str,
    ) -> dict[str, Any] | None:
        """Export a chain and its evidence."""
        chain = self.get_chain(chain_id)
        if chain is None:
            return None
        items = self._evidence.get(chain_id, [])
        return {
            "chain": chain.model_dump(),
            "items": [i.model_dump() for i in items],
            "exported_at": time.time(),
        }

    # -- report --

    def generate_evidence_report(self) -> EvidenceReport:
        """Generate a comprehensive evidence report."""
        total_items = sum(len(items) for items in self._evidence.values())
        intact = sum(1 for c in self._items if c.is_intact)
        broken = len(self._items) - intact
        by_framework: dict[str, int] = {}
        for c in self._items:
            key = c.framework.value
            by_framework[key] = by_framework.get(key, 0) + 1
        by_type: dict[str, int] = {}
        for items in self._evidence.values():
            for item in items:
                key = item.evidence_type.value
                by_type[key] = by_type.get(key, 0) + 1
        by_status: dict[str, int] = {}
        for c in self._items:
            key = c.status.value
            by_status[key] = by_status.get(key, 0) + 1
        recs = self._build_recommendations(
            intact,
            broken,
            total_items,
        )
        return EvidenceReport(
            total_chains=len(self._items),
            total_items=total_items,
            intact_chains=intact,
            broken_chains=broken,
            by_framework=by_framework,
            by_type=by_type,
            by_status=by_status,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns chains cleared."""
        count = len(self._items)
        self._items.clear()
        self._evidence.clear()
        logger.info(
            "evidence_chain.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        total_items = sum(len(items) for items in self._evidence.values())
        fw_dist: dict[str, int] = {}
        for c in self._items:
            key = c.framework.value
            fw_dist[key] = fw_dist.get(key, 0) + 1
        return {
            "total_chains": len(self._items),
            "total_items": total_items,
            "max_chains": self._max_chains,
            "max_items_per_chain": (self._max_items_per_chain),
            "framework_distribution": fw_dist,
        }

    # -- internal helpers --

    def _compute_link_hash(
        self,
        content_hash: str,
        item_id: str,
    ) -> str:
        payload = f"{content_hash}:{item_id}"
        return hashlib.sha256(
            payload.encode(),
        ).hexdigest()

    def _build_recommendations(
        self,
        intact: int,
        broken: int,
        total_items: int,
    ) -> list[str]:
        recs: list[str] = []
        if broken > 0:
            recs.append(f"{broken} broken chain(s) detected - investigate tampering")
        if total_items == 0:
            recs.append("No evidence collected - begin evidence gathering")
        total = intact + broken
        if total > 0:
            pct = round(intact / total * 100, 2)
            if pct < 100:
                recs.append(f"Chain integrity at {pct}% - target 100%")
        if not recs:
            recs.append("All evidence chains intact and verified")
        return recs

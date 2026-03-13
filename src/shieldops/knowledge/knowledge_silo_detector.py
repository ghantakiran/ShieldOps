"""Knowledge Silo Detector —
identify knowledge silos, compute bus factor,
rank domains by concentration risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class KnowledgeArea(StrEnum):
    CODEBASE = "codebase"
    INFRASTRUCTURE = "infrastructure"
    PROCESS = "process"
    DOMAIN = "domain"


class SiloRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConcentrationType(StrEnum):
    SINGLE_PERSON = "single_person"
    SMALL_GROUP = "small_group"
    DISTRIBUTED = "distributed"
    DOCUMENTED = "documented"


# --- Models ---


class KnowledgeSiloRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = ""
    person_id: str = ""
    area: KnowledgeArea = KnowledgeArea.CODEBASE
    risk: SiloRisk = SiloRisk.LOW
    concentration: ConcentrationType = ConcentrationType.DISTRIBUTED
    expertise_level: float = 0.0
    contribution_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeSiloAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = ""
    bus_factor: int = 0
    risk: SiloRisk = SiloRisk.LOW
    concentration: ConcentrationType = ConcentrationType.DISTRIBUTED
    unique_contributors: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeSiloReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_bus_factor: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_concentration: dict[str, int] = Field(default_factory=dict)
    critical_silos: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeSiloDetector:
    """Identify knowledge silos, compute bus factor,
    rank domains by concentration risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[KnowledgeSiloRecord] = []
        self._analyses: dict[str, KnowledgeSiloAnalysis] = {}
        logger.info(
            "knowledge_silo_detector.init",
            max_records=max_records,
        )

    def add_record(
        self,
        domain_id: str = "",
        person_id: str = "",
        area: KnowledgeArea = KnowledgeArea.CODEBASE,
        risk: SiloRisk = SiloRisk.LOW,
        concentration: ConcentrationType = (ConcentrationType.DISTRIBUTED),
        expertise_level: float = 0.0,
        contribution_count: int = 0,
        description: str = "",
    ) -> KnowledgeSiloRecord:
        record = KnowledgeSiloRecord(
            domain_id=domain_id,
            person_id=person_id,
            area=area,
            risk=risk,
            concentration=concentration,
            expertise_level=expertise_level,
            contribution_count=contribution_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_silo.record_added",
            record_id=record.id,
            domain_id=domain_id,
        )
        return record

    def process(self, key: str) -> KnowledgeSiloAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        contributors = set()
        for r in self._records:
            if r.domain_id == rec.domain_id:
                contributors.add(r.person_id)
        bus = len(contributors)
        analysis = KnowledgeSiloAnalysis(
            domain_id=rec.domain_id,
            bus_factor=bus,
            risk=rec.risk,
            concentration=rec.concentration,
            unique_contributors=bus,
            description=(f"Domain {rec.domain_id} bus={bus}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> KnowledgeSiloReport:
        by_a: dict[str, int] = {}
        by_r: dict[str, int] = {}
        by_c: dict[str, int] = {}
        for r in self._records:
            k = r.area.value
            by_a[k] = by_a.get(k, 0) + 1
            k2 = r.risk.value
            by_r[k2] = by_r.get(k2, 0) + 1
            k3 = r.concentration.value
            by_c[k3] = by_c.get(k3, 0) + 1
        domain_people: dict[str, set[str]] = {}
        for r in self._records:
            domain_people.setdefault(r.domain_id, set()).add(r.person_id)
        bus_factors = [len(v) for v in domain_people.values()]
        avg_bf = round(sum(bus_factors) / len(bus_factors), 2) if bus_factors else 0.0
        critical = list(
            {r.domain_id for r in self._records if r.risk in (SiloRisk.CRITICAL, SiloRisk.HIGH)}
        )[:10]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical silos found")
        if not recs:
            recs.append("No critical silos detected")
        return KnowledgeSiloReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_bus_factor=avg_bf,
            by_area=by_a,
            by_risk=by_r,
            by_concentration=by_c,
            critical_silos=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        a_dist: dict[str, int] = {}
        for r in self._records:
            k = r.area.value
            a_dist[k] = a_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "area_distribution": a_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("knowledge_silo_detector.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def identify_knowledge_silos(
        self,
    ) -> list[dict[str, Any]]:
        """Identify domains with concentrated knowledge."""
        domain_people: dict[str, set[str]] = {}
        for r in self._records:
            domain_people.setdefault(r.domain_id, set()).add(r.person_id)
        results: list[dict[str, Any]] = []
        for did, people in domain_people.items():
            if len(people) <= 2:
                results.append(
                    {
                        "domain_id": did,
                        "contributors": len(people),
                        "is_silo": True,
                        "severity": ("critical" if len(people) == 1 else "high"),
                    }
                )
        results.sort(
            key=lambda x: x["contributors"],
        )
        return results

    def compute_bus_factor(
        self,
    ) -> list[dict[str, Any]]:
        """Compute bus factor per domain."""
        domain_people: dict[str, set[str]] = {}
        domain_areas: dict[str, str] = {}
        for r in self._records:
            domain_people.setdefault(r.domain_id, set()).add(r.person_id)
            domain_areas[r.domain_id] = r.area.value
        results: list[dict[str, Any]] = []
        for did, people in domain_people.items():
            results.append(
                {
                    "domain_id": did,
                    "bus_factor": len(people),
                    "area": domain_areas.get(did, ""),
                    "risk": (
                        "critical" if len(people) == 1 else ("high" if len(people) == 2 else "low")
                    ),
                }
            )
        results.sort(
            key=lambda x: x["bus_factor"],
        )
        return results

    def rank_domains_by_concentration_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank domains by knowledge concentration."""
        domain_people: dict[str, set[str]] = {}
        for r in self._records:
            domain_people.setdefault(r.domain_id, set()).add(r.person_id)
        results: list[dict[str, Any]] = []
        for did, people in domain_people.items():
            risk_score = round(100.0 / max(len(people), 1), 2)
            results.append(
                {
                    "domain_id": did,
                    "concentration_risk": risk_score,
                    "contributors": len(people),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["concentration_risk"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results

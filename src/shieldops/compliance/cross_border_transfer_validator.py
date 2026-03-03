"""Cross Border Transfer Validator — validate cross-border data transfer compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TransferMechanism(StrEnum):
    ADEQUACY = "adequacy"
    SCC = "scc"
    BCR = "bcr"
    CONSENT = "consent"
    DEROGATION = "derogation"


class JurisdictionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    PROHIBITED = "prohibited"


class ValidationResult(StrEnum):
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    DENIED = "denied"
    PENDING = "pending"
    REQUIRES_REVIEW = "requires_review"


# --- Models ---


class TransferRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transfer_id: str = ""
    transfer_mechanism: TransferMechanism = TransferMechanism.ADEQUACY
    jurisdiction_risk: JurisdictionRisk = JurisdictionRisk.LOW
    validation_result: ValidationResult = ValidationResult.APPROVED
    compliance_score: float = 0.0
    destination_country: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class TransferAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transfer_id: str = ""
    transfer_mechanism: TransferMechanism = TransferMechanism.ADEQUACY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TransferValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_mechanism: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossBorderTransferValidator:
    """Validate cross-border data transfers; detect non-compliant transfer mechanisms."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TransferRecord] = []
        self._analyses: list[TransferAnalysis] = []
        logger.info(
            "cross_border_transfer_validator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_transfer(
        self,
        transfer_id: str,
        transfer_mechanism: TransferMechanism = TransferMechanism.ADEQUACY,
        jurisdiction_risk: JurisdictionRisk = JurisdictionRisk.LOW,
        validation_result: ValidationResult = ValidationResult.APPROVED,
        compliance_score: float = 0.0,
        destination_country: str = "",
        data_owner: str = "",
    ) -> TransferRecord:
        record = TransferRecord(
            transfer_id=transfer_id,
            transfer_mechanism=transfer_mechanism,
            jurisdiction_risk=jurisdiction_risk,
            validation_result=validation_result,
            compliance_score=compliance_score,
            destination_country=destination_country,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cross_border_transfer_validator.transfer_recorded",
            record_id=record.id,
            transfer_id=transfer_id,
            transfer_mechanism=transfer_mechanism.value,
            jurisdiction_risk=jurisdiction_risk.value,
        )
        return record

    def get_transfer(self, record_id: str) -> TransferRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_transfers(
        self,
        transfer_mechanism: TransferMechanism | None = None,
        jurisdiction_risk: JurisdictionRisk | None = None,
        destination_country: str | None = None,
        limit: int = 50,
    ) -> list[TransferRecord]:
        results = list(self._records)
        if transfer_mechanism is not None:
            results = [r for r in results if r.transfer_mechanism == transfer_mechanism]
        if jurisdiction_risk is not None:
            results = [r for r in results if r.jurisdiction_risk == jurisdiction_risk]
        if destination_country is not None:
            results = [r for r in results if r.destination_country == destination_country]
        return results[-limit:]

    def add_analysis(
        self,
        transfer_id: str,
        transfer_mechanism: TransferMechanism = TransferMechanism.ADEQUACY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TransferAnalysis:
        analysis = TransferAnalysis(
            transfer_id=transfer_id,
            transfer_mechanism=transfer_mechanism,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cross_border_transfer_validator.analysis_added",
            transfer_id=transfer_id,
            transfer_mechanism=transfer_mechanism.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_mechanism_distribution(self) -> dict[str, Any]:
        """Group by transfer_mechanism; return count and avg compliance_score."""
        mech_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.transfer_mechanism.value
            mech_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for mech, scores in mech_data.items():
            result[mech] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_transfer_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "transfer_id": r.transfer_id,
                        "transfer_mechanism": r.transfer_mechanism.value,
                        "compliance_score": r.compliance_score,
                        "destination_country": r.destination_country,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by destination_country, avg compliance_score, sort ascending."""
        country_scores: dict[str, list[float]] = {}
        for r in self._records:
            country_scores.setdefault(r.destination_country, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for country, scores in country_scores.items():
            results.append(
                {
                    "destination_country": country,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_transfer_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> TransferValidationReport:
        by_mechanism: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_mechanism[r.transfer_mechanism.value] = (
                by_mechanism.get(r.transfer_mechanism.value, 0) + 1
            )
            by_risk[r.jurisdiction_risk.value] = by_risk.get(r.jurisdiction_risk.value, 0) + 1
            by_result[r.validation_result.value] = by_result.get(r.validation_result.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.compliance_score < self._threshold)
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_transfer_gaps()
        top_gaps = [o["transfer_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} transfer(s) below compliance threshold ({self._threshold})")
        if self._records and avg_compliance_score < self._threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Cross-border transfer compliance is healthy")
        return TransferValidationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_mechanism=by_mechanism,
            by_risk=by_risk,
            by_result=by_result,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cross_border_transfer_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        mech_dist: dict[str, int] = {}
        for r in self._records:
            key = r.transfer_mechanism.value
            mech_dist[key] = mech_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "mechanism_distribution": mech_dist,
            "unique_countries": len({r.destination_country for r in self._records}),
            "unique_owners": len({r.data_owner for r in self._records}),
        }

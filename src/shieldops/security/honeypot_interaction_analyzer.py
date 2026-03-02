"""Honeypot Interaction Analyzer — classify honeypot interactions, extract TTPs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class InteractionType(StrEnum):
    PORT_SCAN = "port_scan"
    LOGIN_ATTEMPT = "login_attempt"
    FILE_ACCESS = "file_access"
    COMMAND_EXECUTION = "command_execution"
    DATA_EXFILTRATION = "data_exfiltration"


class AttackerSophistication(StrEnum):
    NATION_STATE = "nation_state"
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    SCRIPT_KIDDIE = "script_kiddie"
    AUTOMATED = "automated"


class TTPClassification(StrEnum):
    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    COLLECTION = "collection"


# --- Models ---


class InteractionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    interaction_name: str = ""
    interaction_type: InteractionType = InteractionType.PORT_SCAN
    attacker_sophistication: AttackerSophistication = AttackerSophistication.NATION_STATE
    ttp_classification: TTPClassification = TTPClassification.RECONNAISSANCE
    threat_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class InteractionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    interaction_name: str = ""
    interaction_type: InteractionType = InteractionType.PORT_SCAN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InteractionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_threat_count: int = 0
    avg_threat_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_sophistication: dict[str, int] = Field(default_factory=dict)
    by_ttp: dict[str, int] = Field(default_factory=dict)
    top_high_threat: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class HoneypotInteractionAnalyzer:
    """Classify honeypot interactions, extract TTPs from attacker behaviour."""

    def __init__(
        self,
        max_records: int = 200000,
        threat_score_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._threat_score_threshold = threat_score_threshold
        self._records: list[InteractionRecord] = []
        self._analyses: list[InteractionAnalysis] = []
        logger.info(
            "honeypot_interaction_analyzer.initialized",
            max_records=max_records,
            threat_score_threshold=threat_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_interaction(
        self,
        interaction_name: str,
        interaction_type: InteractionType = InteractionType.PORT_SCAN,
        attacker_sophistication: AttackerSophistication = AttackerSophistication.NATION_STATE,
        ttp_classification: TTPClassification = TTPClassification.RECONNAISSANCE,
        threat_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> InteractionRecord:
        record = InteractionRecord(
            interaction_name=interaction_name,
            interaction_type=interaction_type,
            attacker_sophistication=attacker_sophistication,
            ttp_classification=ttp_classification,
            threat_score=threat_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "honeypot_interaction_analyzer.interaction_recorded",
            record_id=record.id,
            interaction_name=interaction_name,
            interaction_type=interaction_type.value,
            attacker_sophistication=attacker_sophistication.value,
        )
        return record

    def get_interaction(self, record_id: str) -> InteractionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_interactions(
        self,
        interaction_type: InteractionType | None = None,
        attacker_sophistication: AttackerSophistication | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[InteractionRecord]:
        results = list(self._records)
        if interaction_type is not None:
            results = [r for r in results if r.interaction_type == interaction_type]
        if attacker_sophistication is not None:
            results = [r for r in results if r.attacker_sophistication == attacker_sophistication]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        interaction_name: str,
        interaction_type: InteractionType = InteractionType.PORT_SCAN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> InteractionAnalysis:
        analysis = InteractionAnalysis(
            interaction_name=interaction_name,
            interaction_type=interaction_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "honeypot_interaction_analyzer.analysis_added",
            interaction_name=interaction_name,
            interaction_type=interaction_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_interaction_distribution(self) -> dict[str, Any]:
        """Group by interaction_type; return count and avg threat_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.interaction_type.value
            type_data.setdefault(key, []).append(r.threat_score)
        result: dict[str, Any] = {}
        for itype, scores in type_data.items():
            result[itype] = {
                "count": len(scores),
                "avg_threat_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_threat_interactions(self) -> list[dict[str, Any]]:
        """Return records where threat_score > threat_score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_score > self._threat_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "interaction_name": r.interaction_name,
                        "interaction_type": r.interaction_type.value,
                        "threat_score": r.threat_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["threat_score"], reverse=True)

    def rank_by_threat(self) -> list[dict[str, Any]]:
        """Group by service, avg threat_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.threat_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_threat_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_threat_score"], reverse=True)
        return results

    def detect_interaction_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> InteractionReport:
        by_type: dict[str, int] = {}
        by_sophistication: dict[str, int] = {}
        by_ttp: dict[str, int] = {}
        for r in self._records:
            by_type[r.interaction_type.value] = by_type.get(r.interaction_type.value, 0) + 1
            by_sophistication[r.attacker_sophistication.value] = (
                by_sophistication.get(r.attacker_sophistication.value, 0) + 1
            )
            by_ttp[r.ttp_classification.value] = by_ttp.get(r.ttp_classification.value, 0) + 1
        high_threat_count = sum(
            1 for r in self._records if r.threat_score > self._threat_score_threshold
        )
        scores = [r.threat_score for r in self._records]
        avg_threat_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_threat_interactions()
        top_high_threat = [o["interaction_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_threat_count > 0:
            recs.append(
                f"{high_threat_count} interaction(s) above threat threshold "
                f"({self._threat_score_threshold})"
            )
        if self._records and avg_threat_score > self._threat_score_threshold:
            recs.append(
                f"Avg threat score {avg_threat_score} above threshold "
                f"({self._threat_score_threshold})"
            )
        if not recs:
            recs.append("Honeypot interaction threat levels are healthy")
        return InteractionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_threat_count=high_threat_count,
            avg_threat_score=avg_threat_score,
            by_type=by_type,
            by_sophistication=by_sophistication,
            by_ttp=by_ttp,
            top_high_threat=top_high_threat,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("honeypot_interaction_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.interaction_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threat_score_threshold": self._threat_score_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

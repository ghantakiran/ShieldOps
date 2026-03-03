"""Living Off The Land Detector — detect LOLBin abuse via command-line and behavioral analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LOLBinary(StrEnum):
    POWERSHELL = "powershell"
    CERTUTIL = "certutil"
    MSHTA = "mshta"
    REGSVR32 = "regsvr32"
    RUNDLL32 = "rundll32"


class AbusePattern(StrEnum):
    DOWNLOAD = "download"
    EXECUTION = "execution"
    ENCODING = "encoding"
    BYPASS = "bypass"  # noqa: S105
    PERSISTENCE = "persistence"


class DetectionMethod(StrEnum):
    COMMAND_LINE = "command_line"
    PARENT_CHILD = "parent_child"
    BEHAVIORAL = "behavioral"
    SIGNATURE = "signature"
    HEURISTIC = "heuristic"


# --- Models ---


class LOLRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lol_id: str = ""
    lol_binary: LOLBinary = LOLBinary.POWERSHELL
    abuse_pattern: AbusePattern = AbusePattern.DOWNLOAD
    detection_method: DetectionMethod = DetectionMethod.COMMAND_LINE
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LOLAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lol_id: str = ""
    lol_binary: LOLBinary = LOLBinary.POWERSHELL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LOLDetectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_binary: dict[str, int] = Field(default_factory=dict)
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class LivingOffTheLandDetector:
    """Detect LOLBin abuse via command-line analysis and behavioral patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[LOLRecord] = []
        self._analyses: list[LOLAnalysis] = []
        logger.info(
            "living_off_the_land_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_lol(
        self,
        lol_id: str,
        lol_binary: LOLBinary = LOLBinary.POWERSHELL,
        abuse_pattern: AbusePattern = AbusePattern.DOWNLOAD,
        detection_method: DetectionMethod = DetectionMethod.COMMAND_LINE,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LOLRecord:
        record = LOLRecord(
            lol_id=lol_id,
            lol_binary=lol_binary,
            abuse_pattern=abuse_pattern,
            detection_method=detection_method,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "living_off_the_land_detector.lol_recorded",
            record_id=record.id,
            lol_id=lol_id,
            lol_binary=lol_binary.value,
            abuse_pattern=abuse_pattern.value,
        )
        return record

    def get_lol(self, record_id: str) -> LOLRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lols(
        self,
        lol_binary: LOLBinary | None = None,
        abuse_pattern: AbusePattern | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LOLRecord]:
        results = list(self._records)
        if lol_binary is not None:
            results = [r for r in results if r.lol_binary == lol_binary]
        if abuse_pattern is not None:
            results = [r for r in results if r.abuse_pattern == abuse_pattern]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        lol_id: str,
        lol_binary: LOLBinary = LOLBinary.POWERSHELL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LOLAnalysis:
        analysis = LOLAnalysis(
            lol_id=lol_id,
            lol_binary=lol_binary,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "living_off_the_land_detector.analysis_added",
            lol_id=lol_id,
            lol_binary=lol_binary.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_binary_distribution(self) -> dict[str, Any]:
        """Group by lol_binary; return count and avg detection_score."""
        binary_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.lol_binary.value
            binary_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for binary, scores in binary_data.items():
            result[binary] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "lol_id": r.lol_id,
                        "lol_binary": r.lol_binary.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        """Group by service, avg detection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_detection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> LOLDetectionReport:
        by_binary: dict[str, int] = {}
        by_pattern: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_binary[r.lol_binary.value] = by_binary.get(r.lol_binary.value, 0) + 1
            by_pattern[r.abuse_pattern.value] = by_pattern.get(r.abuse_pattern.value, 0) + 1
            by_method[r.detection_method.value] = by_method.get(r.detection_method.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["lol_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} LOL detection(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Living off the land detection is healthy")
        return LOLDetectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_binary=by_binary,
            by_pattern=by_pattern,
            by_method=by_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("living_off_the_land_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        binary_dist: dict[str, int] = {}
        for r in self._records:
            key = r.lol_binary.value
            binary_dist[key] = binary_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "binary_distribution": binary_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

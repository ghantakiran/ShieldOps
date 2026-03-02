"""Adversarial Robustness Tester — test ML model robustness against adversarial attacks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackType(StrEnum):
    EVASION = "evasion"
    POISONING = "poisoning"
    MODEL_EXTRACTION = "model_extraction"
    INFERENCE = "inference"
    BACKDOOR = "backdoor"


class RobustnessLevel(StrEnum):
    ROBUST = "robust"
    MOSTLY_ROBUST = "mostly_robust"
    VULNERABLE = "vulnerable"
    HIGHLY_VULNERABLE = "highly_vulnerable"
    UNKNOWN = "unknown"


class TestStrategy(StrEnum):
    WHITE_BOX = "white_box"
    BLACK_BOX = "black_box"
    GREY_BOX = "grey_box"
    ADAPTIVE = "adaptive"
    TRANSFER = "transfer"


# --- Models ---


class RobustnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    attack_type: AttackType = AttackType.EVASION
    robustness_level: RobustnessLevel = RobustnessLevel.UNKNOWN
    test_strategy: TestStrategy = TestStrategy.BLACK_BOX
    robustness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RobustnessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    attack_type: AttackType = AttackType.EVASION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RobustnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    vulnerable_count: int = 0
    avg_robustness_score: float = 0.0
    by_attack: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_vulnerable: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdversarialRobustnessTester:
    """Test ML model robustness against adversarial attacks."""

    def __init__(
        self,
        max_records: int = 200000,
        robustness_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._robustness_threshold = robustness_threshold
        self._records: list[RobustnessRecord] = []
        self._analyses: list[RobustnessAnalysis] = []
        logger.info(
            "adversarial_robustness_tester.initialized",
            max_records=max_records,
            robustness_threshold=robustness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_test(
        self,
        model_id: str,
        attack_type: AttackType = AttackType.EVASION,
        robustness_level: RobustnessLevel = RobustnessLevel.UNKNOWN,
        test_strategy: TestStrategy = TestStrategy.BLACK_BOX,
        robustness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RobustnessRecord:
        record = RobustnessRecord(
            model_id=model_id,
            attack_type=attack_type,
            robustness_level=robustness_level,
            test_strategy=test_strategy,
            robustness_score=robustness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "adversarial_robustness_tester.test_recorded",
            record_id=record.id,
            model_id=model_id,
            attack_type=attack_type.value,
        )
        return record

    def get_test(self, record_id: str) -> RobustnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_tests(
        self,
        attack_type: AttackType | None = None,
        robustness_level: RobustnessLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RobustnessRecord]:
        results = list(self._records)
        if attack_type is not None:
            results = [r for r in results if r.attack_type == attack_type]
        if robustness_level is not None:
            results = [r for r in results if r.robustness_level == robustness_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        attack_type: AttackType = AttackType.EVASION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RobustnessAnalysis:
        analysis = RobustnessAnalysis(
            model_id=model_id,
            attack_type=attack_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "adversarial_robustness_tester.analysis_added",
            model_id=model_id,
            attack_type=attack_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by attack_type; return count and avg robustness_score."""
        attack_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attack_type.value
            attack_data.setdefault(key, []).append(r.robustness_score)
        result: dict[str, Any] = {}
        for attack, scores in attack_data.items():
            result[attack] = {
                "count": len(scores),
                "avg_robustness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where robustness_score < robustness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.robustness_score < self._robustness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "attack_type": r.attack_type.value,
                        "robustness_score": r.robustness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["robustness_score"])

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg robustness_score, sort ascending (lowest first)."""
        model_scores: dict[str, list[float]] = {}
        for r in self._records:
            model_scores.setdefault(r.model_id, []).append(r.robustness_score)
        results: list[dict[str, Any]] = []
        for model_id, scores in model_scores.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_robustness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_robustness_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RobustnessReport:
        by_attack: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_attack[r.attack_type.value] = by_attack.get(r.attack_type.value, 0) + 1
            by_level[r.robustness_level.value] = by_level.get(r.robustness_level.value, 0) + 1
            by_strategy[r.test_strategy.value] = by_strategy.get(r.test_strategy.value, 0) + 1
        vulnerable_count = sum(
            1 for r in self._records if r.robustness_score < self._robustness_threshold
        )
        scores = [r.robustness_score for r in self._records]
        avg_robustness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        vulnerable_list = self.identify_severe_drifts()
        top_vulnerable = [o["model_id"] for o in vulnerable_list[:5]]
        recs: list[str] = []
        if self._records and vulnerable_count > 0:
            recs.append(
                f"{vulnerable_count} model(s) below robustness threshold "
                f"({self._robustness_threshold})"
            )
        if self._records and avg_robustness_score < self._robustness_threshold:
            recs.append(
                f"Avg robustness score {avg_robustness_score} below threshold "
                f"({self._robustness_threshold})"
            )
        if not recs:
            recs.append("Model robustness is within acceptable bounds")
        return RobustnessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            vulnerable_count=vulnerable_count,
            avg_robustness_score=avg_robustness_score,
            by_attack=by_attack,
            by_level=by_level,
            by_strategy=by_strategy,
            top_vulnerable=top_vulnerable,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("adversarial_robustness_tester.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        attack_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attack_type.value
            attack_dist[key] = attack_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "robustness_threshold": self._robustness_threshold,
            "attack_distribution": attack_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }

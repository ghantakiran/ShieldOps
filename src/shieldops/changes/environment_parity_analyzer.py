"""Environment Parity Analyzer
compute parity scores, detect environment drift,
rank environments by divergence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DISASTER_RECOVERY = "disaster_recovery"


class ParityDimension(StrEnum):
    CONFIG = "config"
    VERSION = "version"
    SCALE = "scale"
    TOPOLOGY = "topology"


class DivergenceLevel(StrEnum):
    IDENTICAL = "identical"
    MINOR = "minor"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


# --- Models ---


class EnvironmentParityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    env_id: str = ""
    env_name: str = ""
    environment_type: EnvironmentType = EnvironmentType.DEVELOPMENT
    parity_dimension: ParityDimension = ParityDimension.CONFIG
    divergence_level: DivergenceLevel = DivergenceLevel.MINOR
    parity_score: float = 0.0
    reference_env: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EnvironmentParityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    env_id: str = ""
    computed_parity: float = 0.0
    divergence_level: DivergenceLevel = DivergenceLevel.MINOR
    dimension_count: int = 0
    needs_attention: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EnvironmentParityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_parity_score: float = 0.0
    by_environment_type: dict[str, int] = Field(default_factory=dict)
    by_parity_dimension: dict[str, int] = Field(default_factory=dict)
    by_divergence_level: dict[str, int] = Field(default_factory=dict)
    divergent_envs: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EnvironmentParityAnalyzer:
    """Compute parity scores, detect environment
    drift, rank environments by divergence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EnvironmentParityRecord] = []
        self._analyses: dict[str, EnvironmentParityAnalysis] = {}
        logger.info(
            "environment_parity_analyzer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        env_id: str = "",
        env_name: str = "",
        environment_type: EnvironmentType = (EnvironmentType.DEVELOPMENT),
        parity_dimension: ParityDimension = (ParityDimension.CONFIG),
        divergence_level: DivergenceLevel = (DivergenceLevel.MINOR),
        parity_score: float = 0.0,
        reference_env: str = "",
        description: str = "",
    ) -> EnvironmentParityRecord:
        record = EnvironmentParityRecord(
            env_id=env_id,
            env_name=env_name,
            environment_type=environment_type,
            parity_dimension=parity_dimension,
            divergence_level=divergence_level,
            parity_score=parity_score,
            reference_env=reference_env,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "environment_parity.record_added",
            record_id=record.id,
            env_id=env_id,
        )
        return record

    def process(self, key: str) -> EnvironmentParityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        dims = sum(1 for r in self._records if r.env_id == rec.env_id)
        needs_att = rec.divergence_level in (
            DivergenceLevel.SIGNIFICANT,
            DivergenceLevel.CRITICAL,
        )
        analysis = EnvironmentParityAnalysis(
            env_id=rec.env_id,
            computed_parity=round(rec.parity_score, 2),
            divergence_level=rec.divergence_level,
            dimension_count=dims,
            needs_attention=needs_att,
            description=(f"Env {rec.env_id} parity {rec.parity_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> EnvironmentParityReport:
        by_et: dict[str, int] = {}
        by_pd: dict[str, int] = {}
        by_dl: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.environment_type.value
            by_et[k] = by_et.get(k, 0) + 1
            k2 = r.parity_dimension.value
            by_pd[k2] = by_pd.get(k2, 0) + 1
            k3 = r.divergence_level.value
            by_dl[k3] = by_dl.get(k3, 0) + 1
            scores.append(r.parity_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        divergent = list(
            {
                r.env_id
                for r in self._records
                if r.divergence_level
                in (
                    DivergenceLevel.SIGNIFICANT,
                    DivergenceLevel.CRITICAL,
                )
            }
        )[:10]
        recs: list[str] = []
        if divergent:
            recs.append(f"{len(divergent)} divergent environments found")
        if not recs:
            recs.append("All environments are in parity")
        return EnvironmentParityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_parity_score=avg,
            by_environment_type=by_et,
            by_parity_dimension=by_pd,
            by_divergence_level=by_dl,
            divergent_envs=divergent,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        et_dist: dict[str, int] = {}
        for r in self._records:
            k = r.environment_type.value
            et_dist[k] = et_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "environment_type_distribution": et_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("environment_parity_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_parity_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute parity score per environment."""
        env_scores: dict[str, list[float]] = {}
        env_types: dict[str, str] = {}
        for r in self._records:
            env_scores.setdefault(r.env_id, []).append(r.parity_score)
            env_types[r.env_id] = r.environment_type.value
        results: list[dict[str, Any]] = []
        for eid, scores in env_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "env_id": eid,
                    "env_type": env_types[eid],
                    "avg_parity": avg,
                    "dimension_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_parity"],
            reverse=True,
        )
        return results

    def detect_environment_drift(
        self,
    ) -> list[dict[str, Any]]:
        """Detect environments with drift."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.divergence_level
                in (
                    DivergenceLevel.SIGNIFICANT,
                    DivergenceLevel.CRITICAL,
                )
                and r.env_id not in seen
            ):
                seen.add(r.env_id)
                results.append(
                    {
                        "env_id": r.env_id,
                        "env_type": (r.environment_type.value),
                        "divergence": (r.divergence_level.value),
                        "parity_score": (r.parity_score),
                        "reference_env": (r.reference_env),
                    }
                )
        results.sort(
            key=lambda x: x["parity_score"],
        )
        return results

    def rank_environments_by_divergence(
        self,
    ) -> list[dict[str, Any]]:
        """Rank environments by divergence."""
        env_data: dict[str, float] = {}
        for r in self._records:
            env_data[r.env_id] = env_data.get(r.env_id, 0.0) + (100.0 - r.parity_score)
        results: list[dict[str, Any]] = []
        for eid, total in env_data.items():
            results.append(
                {
                    "env_id": eid,
                    "divergence_score": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["divergence_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results

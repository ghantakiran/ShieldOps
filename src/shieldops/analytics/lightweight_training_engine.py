"""Lightweight Training Engine

Resource-efficient model training with LoRA, QLoRA,
and distillation support plus budget management.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrainingMode(StrEnum):
    FULL = "full"
    LORA = "lora"
    QLORA = "qlora"
    DISTILLATION = "distillation"


class ResourceConstraint(StrEnum):
    MEMORY = "memory"
    COMPUTE = "compute"
    TIME = "time"
    COST = "cost"


class TrainingPhase(StrEnum):
    WARMUP = "warmup"
    TRAINING = "training"
    COOLDOWN = "cooldown"
    EVALUATION = "evaluation"


# --- Models ---


class TrainingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_name: str = ""
    training_mode: TrainingMode = TrainingMode.LORA
    constraint: ResourceConstraint = ResourceConstraint.MEMORY
    phase: TrainingPhase = TrainingPhase.TRAINING
    loss_value: float = 0.0
    resource_usage_pct: float = 0.0
    epoch: int = 0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class TrainingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_name: str = ""
    training_mode: TrainingMode = TrainingMode.LORA
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TrainingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_loss: float = 0.0
    avg_resource_usage: float = 0.0
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_constraint: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LightweightTrainingEngine:
    """Resource-efficient model training management
    with budget tracking and efficiency metrics.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TrainingRecord] = []
        self._analyses: dict[str, TrainingAnalysis] = {}
        logger.info(
            "lightweight_training_engine.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        job_name: str = "",
        training_mode: TrainingMode = TrainingMode.LORA,
        constraint: ResourceConstraint = (ResourceConstraint.MEMORY),
        phase: TrainingPhase = TrainingPhase.TRAINING,
        loss_value: float = 0.0,
        resource_usage_pct: float = 0.0,
        epoch: int = 0,
        service: str = "",
    ) -> TrainingRecord:
        record = TrainingRecord(
            job_name=job_name,
            training_mode=training_mode,
            constraint=constraint,
            phase=phase,
            loss_value=loss_value,
            resource_usage_pct=resource_usage_pct,
            epoch=epoch,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "lightweight_training_engine.record_added",
            record_id=record.id,
            job_name=job_name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = TrainingAnalysis(
            job_name=rec.job_name,
            training_mode=rec.training_mode,
            analysis_score=rec.loss_value,
            description=(f"Training {rec.job_name} epoch={rec.epoch}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "loss": analysis.analysis_score,
        }

    def generate_report(self) -> TrainingReport:
        by_mode: dict[str, int] = {}
        by_con: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        losses: list[float] = []
        usages: list[float] = []
        for r in self._records:
            m = r.training_mode.value
            by_mode[m] = by_mode.get(m, 0) + 1
            c = r.constraint.value
            by_con[c] = by_con.get(c, 0) + 1
            p = r.phase.value
            by_phase[p] = by_phase.get(p, 0) + 1
            losses.append(r.loss_value)
            usages.append(r.resource_usage_pct)
        avg_loss = round(sum(losses) / len(losses), 4) if losses else 0.0
        avg_usage = round(sum(usages) / len(usages), 4) if usages else 0.0
        recs: list[str] = []
        if avg_usage > 80:
            recs.append("High resource usage — consider LoRA/QLoRA")
        if not recs:
            recs.append("Training pipeline is healthy")
        return TrainingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_loss=avg_loss,
            avg_resource_usage=avg_usage,
            by_mode=by_mode,
            by_constraint=by_con,
            by_phase=by_phase,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        mode_dist: dict[str, int] = {}
        for r in self._records:
            k = r.training_mode.value
            mode_dist[k] = mode_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "mode_distribution": mode_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("lightweight_training_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def estimate_resource_usage(self, job_name: str) -> dict[str, Any]:
        """Estimate resource usage for a training job."""
        matching = [r for r in self._records if r.job_name == job_name]
        if not matching:
            return {
                "job_name": job_name,
                "status": "no_data",
            }
        usages = [r.resource_usage_pct for r in matching]
        return {
            "job_name": job_name,
            "avg_usage": round(sum(usages) / len(usages), 4),
            "max_usage": max(usages),
            "sample_count": len(matching),
        }

    def optimize_batch_schedule(self, job_name: str) -> dict[str, Any]:
        """Optimize batch scheduling for a job."""
        matching = [r for r in self._records if r.job_name == job_name]
        if not matching:
            return {
                "job_name": job_name,
                "status": "no_data",
            }
        by_epoch: dict[int, float] = {}
        for r in matching:
            by_epoch[r.epoch] = r.loss_value
        sorted_epochs = sorted(by_epoch.items())
        return {
            "job_name": job_name,
            "epoch_losses": sorted_epochs,
            "total_epochs": len(sorted_epochs),
        }

    def compute_training_efficiency(self, job_name: str) -> dict[str, Any]:
        """Compute training efficiency metric."""
        matching = [r for r in self._records if r.job_name == job_name]
        if not matching:
            return {
                "job_name": job_name,
                "status": "no_data",
            }
        losses = [r.loss_value for r in matching]
        usages = [r.resource_usage_pct for r in matching]
        avg_loss = sum(losses) / len(losses)
        avg_usage = sum(usages) / len(usages)
        efficiency = round((1 - avg_loss) / max(avg_usage, 0.01), 4)
        return {
            "job_name": job_name,
            "efficiency": efficiency,
            "avg_loss": round(avg_loss, 4),
            "avg_resource_usage": round(avg_usage, 4),
        }

"""CollectorConfigValidator — collector config validation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConfigSection(StrEnum):
    RECEIVERS = "receivers"
    PROCESSORS = "processors"
    EXPORTERS = "exporters"
    EXTENSIONS = "extensions"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEPRECATED = "deprecated"


class ConfigFormat(StrEnum):
    YAML = "yaml"
    JSON = "json"
    ENV = "env"
    CLI = "cli"


# --- Models ---


class CollectorConfigValidatorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    config_section: ConfigSection = ConfigSection.RECEIVERS
    validation_severity: ValidationSeverity = ValidationSeverity.INFO
    config_format: ConfigFormat = ConfigFormat.YAML
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CollectorConfigValidatorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    config_section: ConfigSection = ConfigSection.RECEIVERS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CollectorConfigValidatorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_config_section: dict[str, int] = Field(default_factory=dict)
    by_validation_severity: dict[str, int] = Field(default_factory=dict)
    by_config_format: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CollectorConfigValidator:
    """Collector configuration validation engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CollectorConfigValidatorRecord] = []
        self._analyses: list[CollectorConfigValidatorAnalysis] = []
        logger.info(
            "collector.config.validator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        config_section: ConfigSection = (ConfigSection.RECEIVERS),
        validation_severity: ValidationSeverity = (ValidationSeverity.INFO),
        config_format: ConfigFormat = ConfigFormat.YAML,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CollectorConfigValidatorRecord:
        record = CollectorConfigValidatorRecord(
            name=name,
            config_section=config_section,
            validation_severity=validation_severity,
            config_format=config_format,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "collector.config.validator.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = CollectorConfigValidatorAnalysis(
                    name=r.name,
                    config_section=(r.config_section),
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def validate_pipeline_config(
        self,
    ) -> dict[str, Any]:
        """Validate pipeline config by section."""
        section_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.config_section.value
            section_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in section_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def detect_config_conflicts(
        self,
    ) -> list[dict[str, Any]]:
        """Detect configuration conflicts."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.validation_severity in (
                ValidationSeverity.ERROR,
                ValidationSeverity.WARNING,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "section": (r.config_section.value),
                        "severity": (r.validation_severity.value),
                        "score": r.score,
                    }
                )
        return results

    def recommend_config_fixes(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend configuration fixes."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_score": avg,
                    "fix": ("review_config" if avg < self._threshold else "no_action"),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> CollectorConfigValidatorReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.config_section.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.validation_severity.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.config_format.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Collector Config Validator is healthy")
        return CollectorConfigValidatorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_config_section=by_e1,
            by_validation_severity=by_e2,
            by_config_format=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("collector.config.validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.config_section.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "config_section_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

"""Pydantic state models for the Prediction Agent."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PredictionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrendAnomaly(BaseModel):
    """A detected trend anomaly in metrics or logs."""

    metric_name: str
    resource_id: str = ""
    trend_direction: str = ""  # increasing, decreasing, oscillating
    deviation_percent: float = 0.0
    baseline_value: float = 0.0
    current_value: float = 0.0
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CorrelatedChange(BaseModel):
    """A deployment or config change correlated with the anomaly."""

    change_id: str = ""
    change_type: str = ""  # deployment, config, scaling
    description: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_score: float = 0.0


class Prediction(BaseModel):
    """A predicted incident that hasn't yet triggered an alert."""

    id: str = ""
    title: str = ""
    description: str = ""
    severity: PredictionSeverity = PredictionSeverity.LOW
    confidence: float = 0.0
    predicted_impact: str = ""
    affected_resources: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    estimated_time_to_incident: str = ""  # e.g., "2-4 hours"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PredictionState(BaseModel):
    """State for the Prediction Agent LangGraph workflow."""

    prediction_id: str = ""
    current_step: str = "started"

    # Inputs
    target_resources: list[str] = Field(default_factory=list)
    lookback_hours: int = 24

    # Intermediate state
    trend_anomalies: list[TrendAnomaly] = Field(default_factory=list)
    correlated_changes: list[CorrelatedChange] = Field(default_factory=list)
    risk_score: float = 0.0

    # Output
    predictions: list[Prediction] = Field(default_factory=list)

    # Metadata
    prediction_start: datetime | None = None
    prediction_duration_ms: int = 0
    reasoning_chain: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None

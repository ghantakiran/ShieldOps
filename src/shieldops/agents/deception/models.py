"""State models for the Deception Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeceptionAsset(BaseModel):
    """A deployed deception asset (honeypot, honeytoken, etc.)."""

    asset_id: str = ""
    asset_type: str = ""
    location: str = ""
    status: str = "pending"
    config: dict[str, Any] = Field(default_factory=dict)


class HoneypotInteraction(BaseModel):
    """A recorded interaction with a deception asset."""

    timestamp: str = ""
    source_ip: str = ""
    action: str = ""
    payload_hash: str = ""
    severity: str = "low"


class ReasoningStep(BaseModel):
    """Audit trail entry for the deception workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class DeceptionState(BaseModel):
    """Full state for a deception workflow run through the LangGraph workflow."""

    # Input
    campaign_id: str = ""
    campaign_type: str = ""

    # Asset management
    deployed_assets: list[dict[str, Any]] = Field(default_factory=list)

    # Interaction monitoring
    interactions: list[dict[str, Any]] = Field(default_factory=list)
    interaction_detected: bool = False

    # Analysis
    behavioral_analysis: dict[str, Any] = Field(default_factory=dict)
    extracted_indicators: list[str] = Field(default_factory=list)

    # Response
    severity_level: str = "low"
    containment_triggered: bool = False

    # Strategy
    strategy_updates: list[dict[str, Any]] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None

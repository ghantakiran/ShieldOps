"""State models for the Forensics Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ForensicArtifact(BaseModel):
    """A collected forensic artifact with integrity metadata."""

    artifact_id: str = ""
    source: str = ""
    artifact_type: str = ""
    hash_sha256: str = ""
    integrity_verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningStep(BaseModel):
    """Audit trail entry for the forensics workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class ForensicsState(BaseModel):
    """Full state for a forensics workflow run through the LangGraph workflow."""

    # Input
    incident_id: str = ""
    evidence_ids: list[str] = Field(default_factory=list)

    # Preservation
    preservation_status: dict[str, Any] = Field(default_factory=dict)
    integrity_verified: bool = False

    # Artifact collection
    artifacts: list[dict[str, Any]] = Field(default_factory=list)

    # Analysis findings
    memory_findings: list[dict[str, Any]] = Field(default_factory=list)
    disk_findings: list[dict[str, Any]] = Field(default_factory=list)
    network_findings: list[dict[str, Any]] = Field(default_factory=list)

    # Timeline and IOCs
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    extracted_iocs: list[str] = Field(default_factory=list)

    # Synthesis and reporting
    synthesis: str = ""
    report: dict[str, Any] = Field(default_factory=dict)

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None

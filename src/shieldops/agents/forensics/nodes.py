"""Node implementations for the Forensics Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.forensics.models import (
    ForensicsState,
    ReasoningStep,
)
from shieldops.agents.forensics.tools import ForensicsToolkit

logger = structlog.get_logger()

_toolkit: ForensicsToolkit | None = None


def set_toolkit(toolkit: ForensicsToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> ForensicsToolkit:
    if _toolkit is None:
        return ForensicsToolkit()
    return _toolkit


async def preserve_evidence(state: ForensicsState) -> dict[str, Any]:
    """Preserve evidence and establish chain of custody."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    result = await toolkit.preserve_evidence(state.evidence_ids)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="preserve_evidence",
        input_summary=f"Preserving {len(state.evidence_ids)} evidence items for "
        f"incident {state.incident_id}",
        output_summary=f"Preservation status={result.get('status', 'unknown')}, "
        f"preserved={len(result.get('preserved', []))} items",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="evidence_store",
    )

    return {
        "preservation_status": result,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "preserve_evidence",
        "session_start": start,
    }


async def verify_integrity(state: ForensicsState) -> dict[str, Any]:
    """Verify cryptographic integrity of preserved evidence."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    result = await toolkit.verify_integrity(state.evidence_ids)
    verified = result.get("verified", False)
    discrepancies = result.get("discrepancies", [])

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="verify_integrity",
        input_summary=f"Verifying integrity of {len(state.evidence_ids)} evidence items",
        output_summary=f"Integrity verified={verified}, discrepancies={len(discrepancies)}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="evidence_store",
    )

    return {
        "integrity_verified": verified,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "verify_integrity",
    }


async def collect_artifacts(state: ForensicsState) -> dict[str, Any]:
    """Collect forensic artifacts from all sources."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    memory_artifacts = await toolkit.collect_memory(state.evidence_ids)
    disk_artifacts = await toolkit.collect_disk(state.evidence_ids)
    network_artifacts = await toolkit.collect_network(state.evidence_ids)

    all_artifacts = [
        *[{**a, "source_type": "memory"} for a in memory_artifacts],
        *[{**a, "source_type": "disk"} for a in disk_artifacts],
        *[{**a, "source_type": "network"} for a in network_artifacts],
    ]

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="collect_artifacts",
        input_summary=f"Collecting artifacts from {len(state.evidence_ids)} evidence sources",
        output_summary=f"Collected {len(all_artifacts)} artifacts "
        f"(memory={len(memory_artifacts)}, disk={len(disk_artifacts)}, "
        f"network={len(network_artifacts)})",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="memory_analyzer + disk_analyzer + network_analyzer",
    )

    return {
        "artifacts": all_artifacts,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "collect_artifacts",
    }


async def analyze_memory(state: ForensicsState) -> dict[str, Any]:
    """Analyze volatile memory artifacts."""
    start = datetime.now(UTC)

    memory_artifacts = [a for a in state.artifacts if a.get("source_type") == "memory"]

    findings: list[dict[str, Any]] = []
    for artifact in memory_artifacts:
        findings.append(
            {
                "artifact_id": artifact.get("artifact_id", ""),
                "analysis_type": "memory",
                "processes": [],
                "injected_code": [],
                "network_connections": [],
                "suspicious_regions": [],
            }
        )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_memory",
        input_summary=f"Analyzing {len(memory_artifacts)} memory artifacts",
        output_summary=f"Generated {len(findings)} memory findings",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="memory_analyzer",
    )

    return {
        "memory_findings": findings,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_memory",
    }


async def analyze_disk(state: ForensicsState) -> dict[str, Any]:
    """Analyze disk artifacts (filesystem, registry, deleted files)."""
    start = datetime.now(UTC)

    disk_artifacts = [a for a in state.artifacts if a.get("source_type") == "disk"]

    findings: list[dict[str, Any]] = []
    for artifact in disk_artifacts:
        findings.append(
            {
                "artifact_id": artifact.get("artifact_id", ""),
                "analysis_type": "disk",
                "modified_files": [],
                "deleted_files": [],
                "registry_changes": [],
                "persistence_mechanisms": [],
            }
        )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_disk",
        input_summary=f"Analyzing {len(disk_artifacts)} disk artifacts",
        output_summary=f"Generated {len(findings)} disk findings",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="disk_analyzer",
    )

    return {
        "disk_findings": findings,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_disk",
    }


async def analyze_network(state: ForensicsState) -> dict[str, Any]:
    """Analyze network artifacts (pcap, flow logs, DNS)."""
    start = datetime.now(UTC)

    network_artifacts = [a for a in state.artifacts if a.get("source_type") == "network"]

    findings: list[dict[str, Any]] = []
    for artifact in network_artifacts:
        findings.append(
            {
                "artifact_id": artifact.get("artifact_id", ""),
                "analysis_type": "network",
                "connections": [],
                "dns_queries": [],
                "data_exfiltration": [],
                "c2_indicators": [],
            }
        )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_network",
        input_summary=f"Analyzing {len(network_artifacts)} network artifacts",
        output_summary=f"Generated {len(findings)} network findings",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="network_analyzer",
    )

    return {
        "network_findings": findings,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_network",
    }


async def reconstruct_timeline(state: ForensicsState) -> dict[str, Any]:
    """Reconstruct event timeline from all findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    all_findings = [
        *state.memory_findings,
        *state.disk_findings,
        *state.network_findings,
    ]

    timeline = await toolkit.reconstruct_timeline(all_findings)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="reconstruct_timeline",
        input_summary=f"Reconstructing timeline from {len(all_findings)} findings",
        output_summary=f"Built timeline with {len(timeline)} events",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="timeline_engine",
    )

    return {
        "timeline": timeline,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "reconstruct_timeline",
    }


async def extract_iocs(state: ForensicsState) -> dict[str, Any]:
    """Extract indicators of compromise from all artifacts and findings."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    all_artifacts = [
        *state.artifacts,
        *state.memory_findings,
        *state.disk_findings,
        *state.network_findings,
    ]

    iocs = await toolkit.extract_iocs(all_artifacts)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="extract_iocs",
        input_summary=f"Extracting IOCs from {len(all_artifacts)} artifacts/findings",
        output_summary=f"Extracted {len(iocs)} IOCs",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="ioc_extractor",
    )

    return {
        "extracted_iocs": iocs,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "extract_iocs",
    }


async def synthesize(state: ForensicsState) -> dict[str, Any]:
    """Synthesize all findings into a cohesive forensic summary."""
    start = datetime.now(UTC)

    parts = [f"Forensic investigation for incident {state.incident_id}"]
    parts.append(f"Evidence items analyzed: {len(state.evidence_ids)}")
    parts.append(f"Integrity verified: {state.integrity_verified}")

    if state.memory_findings:
        parts.append(f"Memory findings: {len(state.memory_findings)}")
    if state.disk_findings:
        parts.append(f"Disk findings: {len(state.disk_findings)}")
    if state.network_findings:
        parts.append(f"Network findings: {len(state.network_findings)}")
    if state.timeline:
        parts.append(f"Timeline events: {len(state.timeline)}")
    if state.extracted_iocs:
        parts.append(f"IOCs extracted: {len(state.extracted_iocs)}")

    synthesis = ". ".join(parts)

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="synthesize",
        input_summary=f"Synthesizing findings from {len(state.evidence_ids)} evidence sources",
        output_summary=f"Generated synthesis ({len(synthesis)} chars)",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="llm",
    )

    return {
        "synthesis": synthesis,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "synthesize",
    }


async def generate_report(state: ForensicsState) -> dict[str, Any]:
    """Generate the final forensic investigation report."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    report_data = await toolkit.generate_report(
        {
            "incident_id": state.incident_id,
            "evidence_ids": state.evidence_ids,
            "integrity_verified": state.integrity_verified,
            "memory_findings": state.memory_findings,
            "disk_findings": state.disk_findings,
            "network_findings": state.network_findings,
            "timeline": state.timeline,
            "extracted_iocs": state.extracted_iocs,
            "synthesis": state.synthesis,
        }
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_report",
        input_summary=f"Generating forensic report for incident {state.incident_id}",
        output_summary=f"Report status={report_data.get('status', 'unknown')}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="report_generator",
    )

    return {
        "report": report_data,
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }

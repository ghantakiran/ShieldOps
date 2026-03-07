"""REST API routes for the Security Agent MVP.

Provides endpoints to trigger scans, list vulnerabilities, view
certificate status, list secret findings (masked), and retrieve
Markdown reports.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from shieldops.security_agent import (
    SecurityAgent,
    VulnerabilitySeverity,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["security-agent"])

# Singleton agent — created lazily so the module can be imported without
# side-effects during testing.
_agent: SecurityAgent | None = None


def get_agent() -> SecurityAgent:
    """Return (or create) the SecurityAgent singleton."""
    global _agent
    if _agent is None:
        _agent = SecurityAgent()
    return _agent


def set_agent(agent: SecurityAgent) -> None:
    """Override the agent instance (dependency injection / testing)."""
    global _agent
    _agent = agent


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class ScanRequest(BaseModel):
    """Request body for POST /security/scan."""

    namespace: str = Field("default", description="Kubernetes namespace")
    images: list[str] = Field(
        default_factory=list,
        description="Container images to scan (empty = auto-detect)",
    )
    domains: list[str] = Field(
        default_factory=list,
        description="Domains for TLS certificate checks",
    )
    repo_path: str | None = Field(None, description="Local repo path for secret scanning")


class ScanResponse(BaseModel):
    """Acknowledgement returned when a scan is triggered."""

    scan_id: str
    status: str = "accepted"
    message: str = "Scan started in background."


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/security/scan", response_model=ScanResponse, status_code=202)
async def trigger_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
) -> ScanResponse:
    """Trigger a full security scan. Runs asynchronously."""
    agent = get_agent()

    # Pre-generate the scan_id so we can return it immediately.
    import uuid

    scan_id = str(uuid.uuid4())

    async def _run() -> None:
        result = await agent.run_full_scan(
            namespace=request.namespace,
            images=request.images or None,
            domains=request.domains or None,
            repo_path=request.repo_path,
        )
        # Overwrite scan_id so caller can retrieve the report.
        agent._results[scan_id] = result
        logger.info("security_agent.api.scan_done", scan_id=scan_id)

    background_tasks.add_task(_run)

    return ScanResponse(scan_id=scan_id)


@router.get("/security/vulnerabilities")
async def list_vulnerabilities(
    severity: VulnerabilitySeverity | None = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """List vulnerability findings across all cached scan results."""
    agent = get_agent()
    vulns = []
    for result in agent._results.values():
        vulns.extend(result.vulnerabilities)

    if severity:
        vulns = [v for v in vulns if v.severity == severity]

    vulns = agent.cve_scanner.prioritize_vulnerabilities(vulns)[:limit]
    return {
        "total": len(vulns),
        "vulnerabilities": [v.model_dump(mode="json") for v in vulns],
    }


@router.get("/security/certificates")
async def list_certificates() -> dict[str, Any]:
    """List certificate statuses from all cached scan results."""
    agent = get_agent()
    certs = []
    for result in agent._results.values():
        certs.extend(result.certificates)

    return {
        "total": len(certs),
        "certificates": [c.model_dump(mode="json") for c in certs],
    }


@router.get("/security/secrets")
async def list_secrets() -> dict[str, Any]:
    """List secret findings (masked) from all cached scan results."""
    agent = get_agent()
    secrets = []
    for result in agent._results.values():
        secrets.extend(result.secrets)

    return {
        "total": len(secrets),
        "secrets": [s.model_dump(mode="json") for s in secrets],
    }


@router.get("/security/report/{scan_id}")
async def get_report(scan_id: str) -> dict[str, str]:
    """Return the Markdown security report for a given scan."""
    agent = get_agent()
    result = agent.get_result(scan_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scan {scan_id} not found.",
        )
    report = agent.generate_security_report(result)
    return {"scan_id": scan_id, "report": report}

"""Security posture API endpoints.

Provides REST endpoints for triggering security scans, viewing posture,
browsing CVEs, and checking compliance status.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.security.runner import SecurityRunner
from shieldops.models.base import Environment

router = APIRouter()

# Application-level runner instance
_runner: SecurityRunner | None = None


def get_runner() -> SecurityRunner:
    """Get or create the security runner singleton."""
    global _runner
    if _runner is None:
        _runner = SecurityRunner()
    return _runner


def set_runner(runner: SecurityRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


# --- Request models ---


class TriggerScanRequest(BaseModel):
    """Request body to trigger a security scan."""

    environment: str = "production"
    scan_type: str = "full"  # full, cve_only, credentials_only, compliance_only
    target_resources: list[str] = Field(default_factory=list)
    compliance_frameworks: list[str] = Field(default_factory=list)


# --- Endpoints ---


@router.post("/security/scans", status_code=202)
async def trigger_scan(
    request: TriggerScanRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger a new security scan. Runs asynchronously."""
    runner = get_runner()

    try:
        env = Environment(request.environment)
    except ValueError:
        env = Environment.PRODUCTION

    background_tasks.add_task(
        runner.scan,
        environment=env,
        scan_type=request.scan_type,
        target_resources=request.target_resources or None,
        compliance_frameworks=request.compliance_frameworks or None,
    )

    return {
        "status": "accepted",
        "scan_type": request.scan_type,
        "environment": request.environment,
        "message": "Security scan started. Use GET /security/scans to track progress.",
    }


@router.post("/security/scans/sync")
async def trigger_scan_sync(request: TriggerScanRequest) -> dict:
    """Trigger a security scan and wait for completion."""
    runner = get_runner()

    try:
        env = Environment(request.environment)
    except ValueError:
        env = Environment.PRODUCTION

    result = await runner.scan(
        environment=env,
        scan_type=request.scan_type,
        target_resources=request.target_resources or None,
        compliance_frameworks=request.compliance_frameworks or None,
    )
    return result.model_dump(mode="json")


@router.get("/security/scans")
async def list_scans(
    scan_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List all security scans."""
    runner = get_runner()
    all_scans = runner.list_scans()

    if scan_type:
        all_scans = [s for s in all_scans if s["scan_type"] == scan_type]

    total = len(all_scans)
    paginated = all_scans[offset : offset + limit]

    return {"scans": paginated, "total": total, "limit": limit, "offset": offset}


@router.get("/security/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict:
    """Get full security scan detail."""
    runner = get_runner()
    result = runner.get_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return result.model_dump(mode="json")


@router.get("/security/posture")
async def get_security_posture() -> dict:
    """Get overall security posture from the most recent full scan."""
    runner = get_runner()
    scans = runner.list_scans()

    # Find most recent completed full scan
    completed = [s for s in scans if s["status"] == "complete" and s["scan_type"] == "full"]
    if not completed:
        return {
            "overall_score": 0.0,
            "frameworks": {},
            "critical_cves": 0,
            "pending_patches": 0,
            "credentials_expiring_soon": 0,
            "message": "No completed scans. Trigger a scan first.",
        }

    latest = completed[-1]
    scan_state = runner.get_scan(latest["scan_id"])
    if scan_state and scan_state.posture:
        return scan_state.posture.model_dump(mode="json")

    return {
        "overall_score": latest.get("posture_score", 0),
        "critical_cves": latest.get("critical_cves", 0),
        "credentials_expiring_soon": latest.get("credentials_at_risk", 0),
    }


@router.get("/security/cves")
async def list_cves(
    severity: str | None = None,
    limit: int = 50,
) -> dict:
    """List CVEs from the most recent scan."""
    runner = get_runner()
    scans = runner.list_scans()

    completed = [s for s in scans if s["status"] == "complete"]
    if not completed:
        return {"cves": [], "total": 0}

    scan_state = runner.get_scan(completed[-1]["scan_id"])
    if scan_state is None:
        return {"cves": [], "total": 0}

    cves = scan_state.cve_findings
    if severity:
        cves = [c for c in cves if c.severity == severity]

    total = len(cves)
    return {
        "cves": [c.model_dump(mode="json") for c in cves[:limit]],
        "total": total,
    }


@router.get("/security/compliance/{framework}")
async def get_compliance_status(framework: str) -> dict:
    """Get compliance status for a specific framework."""
    runner = get_runner()
    scans = runner.list_scans()

    completed = [s for s in scans if s["status"] == "complete"]
    if not completed:
        return {"framework": framework, "score": 0.0, "controls": []}

    scan_state = runner.get_scan(completed[-1]["scan_id"])
    if scan_state is None:
        return {"framework": framework, "score": 0.0, "controls": []}

    controls = [
        c.model_dump(mode="json")
        for c in scan_state.compliance_controls
        if c.framework == framework
    ]

    return {
        "framework": framework,
        "score": scan_state.compliance_score,
        "controls": controls,
    }

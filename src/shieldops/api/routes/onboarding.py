"""Onboarding wizard API routes.

Guides new organizations through the initial setup flow:
1. create_org    -- organization name/industry/team size
2. connect_cloud -- validate cloud credentials (AWS/GCP/Azure)
3. deploy_agent  -- deploy a first agent from a template
4. configure_playbook -- select a pre-built playbook (or skip)
5. run_demo      -- trigger a demo investigation
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = structlog.get_logger()
router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

_repository: Any | None = None


def set_repository(repo: Any) -> None:
    """Set the repository instance for onboarding routes."""
    global _repository  # noqa: PLW0603
    _repository = repo


def _get_repo(request: Request) -> Any:
    repo = _repository or getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return repo


# ── Constants ─────────────────────────────────────────────────────


class OnboardingStep(StrEnum):
    CREATE_ORG = "create_org"
    CONNECT_CLOUD = "connect_cloud"
    DEPLOY_AGENT = "deploy_agent"
    CONFIGURE_PLAYBOOK = "configure_playbook"
    RUN_DEMO = "run_demo"


STEP_ORDER: list[str] = [s.value for s in OnboardingStep]

VALID_CLOUD_PROVIDERS = ("aws", "gcp", "azure")
VALID_AGENT_TYPES = (
    "investigation",
    "remediation",
    "security",
    "cost",
    "learning",
    "supervisor",
)


# ── Request / Response models ─────────────────────────────────────


class StepStatus(BaseModel):
    step_name: str
    status: str = "pending"  # pending | completed | skipped
    metadata: dict[str, Any] = Field(default_factory=dict)
    completed_at: str | None = None


class OnboardingState(BaseModel):
    org_id: str
    steps: list[StepStatus]
    current_step: str
    completed: bool


class OnboardingStepUpdate(BaseModel):
    status: str = Field("completed", pattern=r"^(completed|skipped)$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CloudValidationRequest(BaseModel):
    provider: str = Field(..., pattern=r"^(aws|gcp|azure)$")
    credentials: dict[str, str] = Field(
        ...,
        description="Cloud-specific credential fields (keys/tokens)",
    )


class CloudValidationResponse(BaseModel):
    success: bool
    provider: str
    message: str
    services_discovered: list[str] = Field(default_factory=list)


class DeployAgentRequest(BaseModel):
    agent_type: str = Field(
        ...,
        description="Agent type to deploy",
    )
    environment: str = Field("development", max_length=32)


class DeployAgentResponse(BaseModel):
    success: bool
    agent_id: str
    agent_type: str
    environment: str
    message: str


class TriggerDemoRequest(BaseModel):
    scenario: str = Field(
        "high_cpu_alert",
        description="Demo scenario to run",
    )


class TriggerDemoResponse(BaseModel):
    success: bool
    investigation_id: str
    scenario: str
    message: str


# ── Helpers ──────────────────────────────────────────────────────


def _build_onboarding_state(
    org_id: str,
    progress: list[dict[str, Any]],
) -> OnboardingState:
    """Build an OnboardingState from DB records, filling in missing steps."""
    step_map: dict[str, dict[str, Any]] = {r["step_name"]: r for r in progress}

    steps: list[StepStatus] = []
    for step_name in STEP_ORDER:
        record = step_map.get(step_name)
        if record is not None:
            steps.append(
                StepStatus(
                    step_name=record["step_name"],
                    status=record["status"],
                    metadata=record.get("metadata") or {},
                    completed_at=record.get("completed_at"),
                )
            )
        else:
            steps.append(StepStatus(step_name=step_name, status="pending"))

    # Determine current step: first non-completed/non-skipped
    current_step = STEP_ORDER[-1]
    all_done = True
    for s in steps:
        if s.status not in ("completed", "skipped"):
            current_step = s.step_name
            all_done = False
            break

    return OnboardingState(
        org_id=org_id,
        steps=steps,
        current_step=current_step,
        completed=all_done,
    )


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/status")
async def get_onboarding_status(
    request: Request,
    org_id: str = "default",
) -> OnboardingState:
    """Return the current onboarding state for an organization."""
    repo = _get_repo(request)
    progress = await repo.get_onboarding_progress(org_id)
    return _build_onboarding_state(org_id, progress)


@router.post("/step/{step_name}")
async def complete_step(
    request: Request,
    step_name: str,
    body: OnboardingStepUpdate,
    org_id: str = "default",
) -> OnboardingState:
    """Mark an onboarding step as completed or skipped."""
    if step_name not in STEP_ORDER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step name: {step_name}. Valid steps: {STEP_ORDER}",
        )

    repo = _get_repo(request)

    # Validate step-specific metadata
    if step_name == OnboardingStep.CREATE_ORG and body.status == "completed":
        name = body.metadata.get("name")
        if not name or not isinstance(name, str) or len(name.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Organization name is required in metadata",
            )

    await repo.update_onboarding_step(
        org_id=org_id,
        step=step_name,
        status=body.status,
        metadata=body.metadata,
    )

    progress = await repo.get_onboarding_progress(org_id)
    state = _build_onboarding_state(org_id, progress)

    # Mark org onboarding_completed if all steps are done
    if state.completed:
        try:
            await repo.update_organization(
                org_id,
                settings={"onboarding_completed": True},
            )
            logger.info("onboarding_completed", org_id=org_id)
        except Exception:
            logger.debug("onboarding_org_update_skipped", org_id=org_id)

    return state


@router.post("/validate-cloud")
async def validate_cloud_credentials(
    request: Request,
    body: CloudValidationRequest,
    org_id: str = "default",
) -> CloudValidationResponse:
    """Test cloud credentials and return validation result.

    In production this would call the actual cloud provider APIs.
    For onboarding, we validate the credential shape and return
    a simulated success/failure.
    """
    repo = _get_repo(request)
    provider = body.provider

    # Validate credential fields per provider
    required_fields: dict[str, list[str]] = {
        "aws": ["access_key_id", "secret_access_key"],
        "gcp": ["project_id", "service_account_key"],
        "azure": ["subscription_id", "tenant_id", "client_id"],
    }

    missing = [f for f in required_fields.get(provider, []) if not body.credentials.get(f)]
    if missing:
        return CloudValidationResponse(
            success=False,
            provider=provider,
            message=f"Missing required credential fields: {', '.join(missing)}",
        )

    # Simulated service discovery per provider
    services_discovered: dict[str, list[str]] = {
        "aws": ["EC2", "S3", "RDS", "Lambda", "CloudWatch"],
        "gcp": ["Compute Engine", "Cloud Storage", "Cloud SQL", "Cloud Functions"],
        "azure": ["Virtual Machines", "Blob Storage", "SQL Database", "Functions"],
    }

    # Persist the cloud connection step
    await repo.update_onboarding_step(
        org_id=org_id,
        step=OnboardingStep.CONNECT_CLOUD,
        status="completed",
        metadata={
            "provider": provider,
            "services_discovered": services_discovered.get(provider, []),
        },
    )

    logger.info("cloud_credentials_validated", org_id=org_id, provider=provider)
    return CloudValidationResponse(
        success=True,
        provider=provider,
        message=f"Successfully connected to {provider.upper()}",
        services_discovered=services_discovered.get(provider, []),
    )


@router.post("/deploy-agent")
async def deploy_first_agent(
    request: Request,
    body: DeployAgentRequest,
    org_id: str = "default",
) -> DeployAgentResponse:
    """Deploy the first agent for this organization.

    In production this would call the AgentRegistry. For onboarding
    we simulate a successful deployment and record the step.
    """
    if body.agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent type: {body.agent_type}. Valid types: {list(VALID_AGENT_TYPES)}",
        )

    repo = _get_repo(request)

    from uuid import uuid4

    agent_id = f"agt-{uuid4().hex[:12]}"

    await repo.update_onboarding_step(
        org_id=org_id,
        step=OnboardingStep.DEPLOY_AGENT,
        status="completed",
        metadata={
            "agent_id": agent_id,
            "agent_type": body.agent_type,
            "environment": body.environment,
        },
    )

    logger.info(
        "onboarding_agent_deployed",
        org_id=org_id,
        agent_id=agent_id,
        agent_type=body.agent_type,
    )
    return DeployAgentResponse(
        success=True,
        agent_id=agent_id,
        agent_type=body.agent_type,
        environment=body.environment,
        message=f"{body.agent_type.capitalize()} agent deployed successfully",
    )


@router.post("/trigger-demo")
async def trigger_demo_investigation(
    request: Request,
    body: TriggerDemoRequest | None = None,
    org_id: str = "default",
) -> TriggerDemoResponse:
    """Trigger a demo investigation to showcase the platform.

    In production this would invoke the InvestigationRunner. For onboarding
    we simulate a demo investigation and record the step.
    """
    repo = _get_repo(request)
    scenario = body.scenario if body else "high_cpu_alert"

    from uuid import uuid4

    investigation_id = f"inv-demo-{uuid4().hex[:8]}"

    await repo.update_onboarding_step(
        org_id=org_id,
        step=OnboardingStep.RUN_DEMO,
        status="completed",
        metadata={
            "investigation_id": investigation_id,
            "scenario": scenario,
        },
    )

    logger.info(
        "onboarding_demo_triggered",
        org_id=org_id,
        investigation_id=investigation_id,
        scenario=scenario,
    )
    return TriggerDemoResponse(
        success=True,
        investigation_id=investigation_id,
        scenario=scenario,
        message=f"Demo investigation '{scenario}' started successfully",
    )

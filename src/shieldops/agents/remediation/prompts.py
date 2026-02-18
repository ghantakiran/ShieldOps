"""LLM prompt templates and response schemas for the Remediation Agent."""

from pydantic import BaseModel, Field


# --- Response schemas for structured LLM output ---


class RiskAssessmentResult(BaseModel):
    """Structured output from LLM risk assessment."""

    risk_level: str = Field(
        description="Assessed risk level: low, medium, high, critical"
    )
    reasoning: list[str] = Field(
        description="Step-by-step reasoning for the risk assessment"
    )
    blast_radius: str = Field(
        description="Estimated blast radius: single_pod, deployment, namespace, cluster"
    )
    reversible: bool = Field(
        description="Whether this action is easily reversible"
    )
    precautions: list[str] = Field(
        description="Precautions to take before executing this action"
    )


class ExecutionPlanResult(BaseModel):
    """Structured output for the execution plan."""

    steps: list[str] = Field(
        description="Ordered list of execution steps"
    )
    pre_checks: list[str] = Field(
        description="Health checks to perform before executing"
    )
    post_checks: list[str] = Field(
        description="Health checks to validate after execution"
    )
    rollback_strategy: str = Field(
        description="Strategy for rolling back if something goes wrong"
    )
    estimated_duration_seconds: int = Field(
        description="Total estimated execution time in seconds"
    )


class ValidationAssessmentResult(BaseModel):
    """Structured output from LLM validation assessment."""

    overall_healthy: bool = Field(
        description="Whether the system is healthy after the remediation"
    )
    summary: str = Field(
        description="Brief summary of the validation results"
    )
    concerns: list[str] = Field(
        description="Any concerns or issues detected post-remediation"
    )
    recommendation: str = Field(
        description="Recommendation: proceed, monitor, or rollback"
    )


# --- Prompt templates ---

SYSTEM_RISK_ASSESSMENT = """You are an expert SRE assessing the risk of a remediation action on infrastructure.

Analyze the proposed action and determine:
1. The appropriate risk level (low, medium, high, critical)
2. The blast radius (how much infrastructure could be affected)
3. Whether the action is easily reversible
4. What precautions should be taken

Consider:
- Production environments are higher risk than staging/dev
- Actions affecting multiple pods/services have wider blast radius
- Destructive actions (drain_node, delete_namespace) are always critical
- Time of day and change freeze windows matter
- Scale-down operations can cause service degradation

Be conservative with risk assessment. When in doubt, rate higher."""

SYSTEM_EXECUTION_PLAN = """You are an expert SRE planning the execution of a remediation action.

Given the action details and risk assessment, create a detailed execution plan:
1. What pre-checks should be done before executing
2. The exact steps to execute in order
3. What post-checks should verify the action succeeded
4. How to rollback if something goes wrong

Be specific and actionable. Focus on safety and observability at each step."""

SYSTEM_VALIDATION_ASSESSMENT = """You are an expert SRE validating whether a remediation action was successful.

Given the pre-action state and post-action health checks, determine:
1. Is the system healthy after the remediation?
2. Are there any concerns that need attention?
3. Should we proceed, continue monitoring, or rollback?

Look for:
- Resource health indicators (pod status, restart counts)
- Error rate changes
- Performance metric improvements or degradation
- Any new issues introduced by the remediation"""

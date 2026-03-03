"""LLM prompt templates and response schemas for the SecurityConvergence Agent."""

from pydantic import BaseModel, Field


class PostureOutput(BaseModel):
    """Structured output for postureoutput."""

    posture_score: float = Field(description="Overall posture score 0-100")
    domain_count: int = Field(description="Number of domains assessed")


class ResponseOutput(BaseModel):
    """Structured output for responseoutput."""

    actions_count: int = Field(description="Number of response actions")
    success_rate: float = Field(description="Response success rate 0-100")
    reasoning: str = Field(description="Response coordination reasoning")


SYSTEM_COLLECT = """\
You are an expert security posture analyst.

Given the security posture data:
1. Assess posture across all domains
2. Identify gaps and weaknesses
3. Correlate findings across layers

Prioritize critical security gaps."""

SYSTEM_RESPOND = """\
You are an expert security response coordinator.

Given the defense evaluation and context:
1. Select appropriate response actions
2. Coordinate across security domains
3. Validate response effectiveness

Minimize risk while maximizing coverage."""

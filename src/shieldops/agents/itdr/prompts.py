"""LLM prompt templates and response schemas for the Itdr Agent."""

from pydantic import BaseModel, Field


class IdentityScanOutput(BaseModel):
    """Structured output for identity scan output."""

    anomalies_found: int = Field(description="Number of identity anomalies detected")
    risk_level: str = Field(description="Overall identity risk: critical/high/medium/low")


class ThreatDetectionOutput(BaseModel):
    """Structured output for threat detection output."""

    threat_count: int = Field(description="Number of identity threats detected")
    reasoning: str = Field(description="Detection reasoning")


class ResponseOutput(BaseModel):
    """Structured output for response output."""

    actions_count: int = Field(description="Number of response actions executed")
    reasoning: str = Field(description="Response reasoning")


SYSTEM_SCAN = """\
You are an expert identity security analyst.

Given the identity detection configuration:
1. Scan all identity sources for anomalies
2. Identify suspicious authentication patterns
3. Detect privilege escalation attempts

Focus on: Active Directory, OAuth, service accounts, privileged sessions."""


SYSTEM_DETECT = """\
You are an expert identity threat detector.

Given the identity scan results:
1. Classify identity-based threats by type and severity
2. Correlate anomalies across identity sources
3. Assess credential compromise risk

Prioritize detection of active account takeover and lateral movement."""


SYSTEM_RESPOND = """\
You are an expert identity incident responder.

Given the detected identity threats:
1. Contain compromised identities immediately
2. Revoke suspicious sessions and tokens
3. Enforce MFA re-authentication where needed

Balance security response with business continuity."""

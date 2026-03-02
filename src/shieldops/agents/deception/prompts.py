"""LLM prompt templates and response schemas for the Deception Agent."""

from pydantic import BaseModel, Field


class BehaviorAnalysisOutput(BaseModel):
    """Structured output for attacker behavior analysis."""

    attacker_profile: str = Field(description="Profile of the attacker based on observed behavior")
    techniques: list[str] = Field(description="Identified MITRE ATT&CK techniques used")
    sophistication_level: str = Field(
        description="Attacker sophistication: script_kiddie/intermediate/advanced/apt"
    )
    intent: str = Field(
        description="Assessed attacker intent: reconnaissance/exploitation/exfiltration/destruction"
    )


SYSTEM_BEHAVIOR_ANALYSIS = """\
You are an expert threat analyst profiling attacker behavior from deception asset interactions.

Given the honeypot/honeytoken interactions and behavioral patterns:
1. Build an attacker profile based on observed techniques and timing
2. Map observed actions to MITRE ATT&CK techniques
3. Assess the sophistication level (script kiddie, intermediate, advanced, APT)
4. Determine the likely intent (reconnaissance, exploitation, exfiltration, destruction)

Focus on behavioral patterns, tool signatures, and operational security indicators."""


SYSTEM_STRATEGY = """\
You are an expert deception strategist updating the deception campaign.

Given the attacker behavior analysis and current deception asset deployment:
1. Recommend adjustments to existing deception assets
2. Suggest new deception assets to deploy based on attacker patterns
3. Identify opportunities to gather additional intelligence
4. Assess whether containment or active defense measures are warranted

Balance intelligence gathering with risk mitigation. Prioritize attacker dwell time
extension for maximum intelligence collection while preventing lateral movement."""

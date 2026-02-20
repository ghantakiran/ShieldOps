"""SDK resource modules -- one per API domain."""

from __future__ import annotations

from shieldops_sdk.resources.agents import AgentsResource, AsyncAgentsResource
from shieldops_sdk.resources.investigations import (
    AsyncInvestigationsResource,
    InvestigationsResource,
)
from shieldops_sdk.resources.remediations import (
    AsyncRemediationsResource,
    RemediationsResource,
)
from shieldops_sdk.resources.security import AsyncSecurityResource, SecurityResource
from shieldops_sdk.resources.vulnerabilities import (
    AsyncVulnerabilitiesResource,
    VulnerabilitiesResource,
)

__all__ = [
    "AgentsResource",
    "AsyncAgentsResource",
    "AsyncInvestigationsResource",
    "AsyncRemediationsResource",
    "AsyncSecurityResource",
    "AsyncVulnerabilitiesResource",
    "InvestigationsResource",
    "RemediationsResource",
    "SecurityResource",
    "VulnerabilitiesResource",
]

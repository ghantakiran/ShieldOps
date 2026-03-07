"""ShieldOps Investigate -- Open Source K8s Investigation Toolkit.

AI-powered root cause analysis for Kubernetes incidents.
From alert to diagnosis in under 60 seconds.
"""

from shieldops_investigate.investigator import Investigator
from shieldops_investigate.models import Evidence, Hypothesis, InvestigationResult

__version__ = "0.1.0"
__all__ = ["Evidence", "Hypothesis", "InvestigationResult", "Investigator"]

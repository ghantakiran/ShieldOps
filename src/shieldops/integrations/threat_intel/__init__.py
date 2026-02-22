"""Threat intelligence integrations: MITRE ATT&CK mapping and EPSS scoring."""

from shieldops.integrations.threat_intel.epss import EPSSScorer
from shieldops.integrations.threat_intel.mitre_attack import MITREAttackMapper

__all__ = ["EPSSScorer", "MITREAttackMapper"]

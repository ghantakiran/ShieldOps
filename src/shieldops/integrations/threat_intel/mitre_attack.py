"""MITRE ATT&CK threat intelligence mapper.

Maps CVEs to MITRE ATT&CK techniques via CWE → CAPEC → ATT&CK lookups,
providing attack-context enrichment for vulnerability findings.
"""

from typing import Any

import structlog

logger = structlog.get_logger()

# CWE → CAPEC mapping (common weakness → attack pattern)
CWE_TO_CAPEC: dict[str, list[str]] = {
    "CWE-79": ["CAPEC-86", "CAPEC-198"],  # XSS
    "CWE-89": ["CAPEC-66", "CAPEC-108"],  # SQL Injection
    "CWE-78": ["CAPEC-88"],  # OS Command Injection
    "CWE-22": ["CAPEC-126"],  # Path Traversal
    "CWE-287": ["CAPEC-114", "CAPEC-151"],  # Improper Auth
    "CWE-269": ["CAPEC-122"],  # Privilege Escalation
    "CWE-200": ["CAPEC-116", "CAPEC-169"],  # Info Exposure
    "CWE-502": ["CAPEC-586"],  # Deserialization
    "CWE-918": ["CAPEC-664"],  # SSRF
    "CWE-611": ["CAPEC-201"],  # XXE
    "CWE-94": ["CAPEC-242"],  # Code Injection
    "CWE-434": ["CAPEC-1"],  # Unrestricted Upload
    "CWE-352": ["CAPEC-62"],  # CSRF
    "CWE-862": ["CAPEC-122"],  # Missing Authorization
    "CWE-798": ["CAPEC-70"],  # Hard-coded Credentials
    "CWE-306": ["CAPEC-115"],  # Missing Auth for Critical Function
    "CWE-119": ["CAPEC-100"],  # Buffer Overflow
    "CWE-120": ["CAPEC-100"],  # Buffer Overflow (classic)
    "CWE-416": ["CAPEC-100"],  # Use After Free
}

# CAPEC → ATT&CK Technique mapping
CAPEC_TO_ATTACK: dict[str, list[dict[str, str]]] = {
    "CAPEC-66": [
        {
            "technique_id": "T1190",
            "name": "Exploit Public-Facing Application",
            "tactic": "Initial Access",
        },
    ],
    "CAPEC-86": [
        {"technique_id": "T1189", "name": "Drive-by Compromise", "tactic": "Initial Access"},
        {"technique_id": "T1059.007", "name": "JavaScript", "tactic": "Execution"},
    ],
    "CAPEC-88": [
        {
            "technique_id": "T1059",
            "name": "Command and Scripting Interpreter",
            "tactic": "Execution",
        },
    ],
    "CAPEC-100": [
        {
            "technique_id": "T1203",
            "name": "Exploitation for Client Execution",
            "tactic": "Execution",
        },
    ],
    "CAPEC-108": [
        {
            "technique_id": "T1190",
            "name": "Exploit Public-Facing Application",
            "tactic": "Initial Access",
        },
    ],
    "CAPEC-114": [
        {"technique_id": "T1078", "name": "Valid Accounts", "tactic": "Persistence"},
    ],
    "CAPEC-115": [
        {"technique_id": "T1078", "name": "Valid Accounts", "tactic": "Persistence"},
    ],
    "CAPEC-116": [
        {"technique_id": "T1005", "name": "Data from Local System", "tactic": "Collection"},
    ],
    "CAPEC-122": [
        {
            "technique_id": "T1068",
            "name": "Exploitation for Privilege Escalation",
            "tactic": "Privilege Escalation",
        },
    ],
    "CAPEC-126": [
        {"technique_id": "T1083", "name": "File and Directory Discovery", "tactic": "Discovery"},
    ],
    "CAPEC-151": [
        {"technique_id": "T1110", "name": "Brute Force", "tactic": "Credential Access"},
    ],
    "CAPEC-169": [
        {"technique_id": "T1530", "name": "Data from Cloud Storage Object", "tactic": "Collection"},
    ],
    "CAPEC-198": [
        {"technique_id": "T1189", "name": "Drive-by Compromise", "tactic": "Initial Access"},
    ],
    "CAPEC-201": [
        {
            "technique_id": "T1190",
            "name": "Exploit Public-Facing Application",
            "tactic": "Initial Access",
        },
    ],
    "CAPEC-242": [
        {
            "technique_id": "T1059",
            "name": "Command and Scripting Interpreter",
            "tactic": "Execution",
        },
    ],
    "CAPEC-586": [
        {
            "technique_id": "T1190",
            "name": "Exploit Public-Facing Application",
            "tactic": "Initial Access",
        },
    ],
    "CAPEC-664": [
        {
            "technique_id": "T1190",
            "name": "Exploit Public-Facing Application",
            "tactic": "Initial Access",
        },
    ],
    "CAPEC-1": [
        {"technique_id": "T1105", "name": "Ingress Tool Transfer", "tactic": "Command and Control"},
    ],
    "CAPEC-62": [
        {"technique_id": "T1189", "name": "Drive-by Compromise", "tactic": "Initial Access"},
    ],
    "CAPEC-70": [
        {"technique_id": "T1078", "name": "Valid Accounts", "tactic": "Persistence"},
    ],
}


class MITREAttackMapper:
    """Maps CVEs to MITRE ATT&CK techniques via CWE → CAPEC → ATT&CK.

    Provides context about how a vulnerability might be exploited in
    a real-world attack chain.
    """

    def map_cve(self, cve_data: dict[str, Any]) -> dict[str, Any]:
        """Map a CVE finding to MITRE ATT&CK techniques.

        Args:
            cve_data: Dict with at least one of: ``cwes``, ``cwe_id``, ``description``.

        Returns:
            Dict with attack_techniques, tactics, capec_ids, and risk_context.
        """
        cwes = self._extract_cwes(cve_data)
        capecs = self._cwes_to_capecs(cwes)
        techniques = self._capecs_to_techniques(capecs)

        # Deduplicate techniques
        seen: set[str] = set()
        unique_techniques: list[dict[str, str]] = []
        for tech in techniques:
            if tech["technique_id"] not in seen:
                seen.add(tech["technique_id"])
                unique_techniques.append(tech)

        tactics = sorted({t["tactic"] for t in unique_techniques})

        return {
            "cve_id": cve_data.get("cve_id", ""),
            "cwes": cwes,
            "capec_ids": capecs,
            "attack_techniques": unique_techniques,
            "tactics": tactics,
            "technique_count": len(unique_techniques),
            "risk_context": self._build_risk_context(unique_techniques, tactics),
        }

    def get_technique(self, technique_id: str) -> dict[str, Any] | None:
        """Look up a single ATT&CK technique by ID."""
        for capec_techniques in CAPEC_TO_ATTACK.values():
            for tech in capec_techniques:
                if tech["technique_id"] == technique_id:
                    return {
                        "technique_id": tech["technique_id"],
                        "name": tech["name"],
                        "tactic": tech["tactic"],
                    }
        return None

    def get_tactic_summary(self, tactics: list[str]) -> dict[str, str]:
        """Return human-readable descriptions for a list of tactics."""
        descriptions: dict[str, str] = {
            "Initial Access": "Adversary gains entry to the network/system",
            "Execution": "Adversary runs malicious code",
            "Persistence": "Adversary maintains access across restarts",
            "Privilege Escalation": "Adversary gains higher-level permissions",
            "Defense Evasion": "Adversary avoids detection",
            "Credential Access": "Adversary steals credentials",
            "Discovery": "Adversary explores the environment",
            "Lateral Movement": "Adversary moves through the network",
            "Collection": "Adversary gathers target data",
            "Command and Control": "Adversary communicates with compromised systems",
            "Exfiltration": "Adversary steals data out of the network",
            "Impact": "Adversary disrupts availability or integrity",
        }
        return {t: descriptions.get(t, "Unknown tactic") for t in tactics}

    def _extract_cwes(self, cve_data: dict[str, Any]) -> list[str]:
        """Extract CWE IDs from CVE data."""
        cwes: list[str] = []

        # Direct list of CWEs
        if "cwes" in cve_data:
            for cwe in cve_data["cwes"]:
                if isinstance(cwe, str):
                    cwes.append(cwe if cwe.startswith("CWE-") else f"CWE-{cwe}")
                elif isinstance(cwe, dict):
                    cwe_id = cwe.get("id", cwe.get("cwe_id", ""))
                    if cwe_id:
                        cwes.append(cwe_id if cwe_id.startswith("CWE-") else f"CWE-{cwe_id}")

        # Single CWE
        if "cwe_id" in cve_data and cve_data["cwe_id"]:
            cwe_id = cve_data["cwe_id"]
            normalized = cwe_id if cwe_id.startswith("CWE-") else f"CWE-{cwe_id}"
            if normalized not in cwes:
                cwes.append(normalized)

        # Infer CWE from description if none found
        if not cwes:
            cwes = self._infer_cwes_from_description(cve_data.get("description", ""))

        return cwes

    def _infer_cwes_from_description(self, description: str) -> list[str]:
        """Infer CWE from vulnerability description keywords."""
        desc_lower = description.lower()
        inferred: list[str] = []

        keyword_map = {
            "sql injection": "CWE-89",
            "cross-site scripting": "CWE-79",
            "xss": "CWE-79",
            "command injection": "CWE-78",
            "path traversal": "CWE-22",
            "directory traversal": "CWE-22",
            "buffer overflow": "CWE-119",
            "use after free": "CWE-416",
            "deserialization": "CWE-502",
            "ssrf": "CWE-918",
            "xxe": "CWE-611",
            "csrf": "CWE-352",
            "authentication bypass": "CWE-287",
            "privilege escalation": "CWE-269",
            "hard-coded": "CWE-798",
            "hardcoded": "CWE-798",
            "information disclosure": "CWE-200",
            "unrestricted upload": "CWE-434",
        }

        for keyword, cwe in keyword_map.items():
            if keyword in desc_lower and cwe not in inferred:
                inferred.append(cwe)

        return inferred

    def _cwes_to_capecs(self, cwes: list[str]) -> list[str]:
        capecs: list[str] = []
        for cwe in cwes:
            for capec in CWE_TO_CAPEC.get(cwe, []):
                if capec not in capecs:
                    capecs.append(capec)
        return capecs

    def _capecs_to_techniques(self, capecs: list[str]) -> list[dict[str, str]]:
        techniques: list[dict[str, str]] = []
        for capec in capecs:
            techniques.extend(CAPEC_TO_ATTACK.get(capec, []))
        return techniques

    def _build_risk_context(self, techniques: list[dict[str, str]], tactics: list[str]) -> str:
        if not techniques:
            return "No known ATT&CK mapping. Manual threat assessment recommended."

        parts: list[str] = []
        if "Initial Access" in tactics:
            parts.append("exploitable for initial network entry")
        if "Execution" in tactics:
            parts.append("enables code execution")
        if "Privilege Escalation" in tactics:
            parts.append("allows privilege escalation")
        if "Credential Access" in tactics:
            parts.append("may enable credential theft")
        if "Collection" in tactics or "Exfiltration" in tactics:
            parts.append("risk of data exfiltration")

        if parts:
            return (
                f"This vulnerability is {', '.join(parts)}. "
                f"{len(techniques)} ATT&CK technique(s) mapped across "
                f"{len(tactics)} tactic(s)."
            )
        return f"{len(techniques)} ATT&CK technique(s) mapped across {len(tactics)} tactic(s)."

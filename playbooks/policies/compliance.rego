# ShieldOps Compliance Mapping Policy
# Maps agent actions to compliance framework controls (SOC2, PCI-DSS, HIPAA, CIS)
# and evaluates whether compliance requirements are met.

package shieldops

import rego.v1

# --- Action category sets ---

patching_actions := {
    "patch_package",
    "update_service",
    "force_new_deployment",
    "apply_security_patch",
}

credential_actions := {
    "rotate_credentials",
    "revoke_access",
    "update_iam_policy",
}

monitoring_actions := {
    "get_health",
    "query_metrics",
    "query_logs",
    "detect_anomalies",
}

k8s_pod_actions := {
    "restart_pod",
    "scale_horizontal",
    "drain_node",
    "rollback_deployment",
}

# --- Rule 1: compliance_controls ---
# Set of control IDs relevant to the current action.

compliance_controls contains "SOC2-CC8.1" if {
    not input.action in read_only_actions
}

compliance_controls contains "PCI-DSS-6.2" if {
    input.action in patching_actions
}

compliance_controls contains "PCI-DSS-10.1" if {
    true
}

compliance_controls contains "HIPAA-164.312a" if {
    input.action in credential_actions
}

compliance_controls contains "SOC2-CC7.1" if {
    input.action in monitoring_actions
}

compliance_controls contains "CIS-5.2" if {
    input.action in k8s_pod_actions
}

# --- Rule 2: compliance_violations ---
# Set of {control, reason} objects for controls that are violated.

compliance_violations contains {"control": "SOC2-CC8.1", "reason": "Mutating action in production requires approval"} if {
    not input.action in read_only_actions
    input.environment == "production"
    not input.context.approval_status == "approved"
}

compliance_violations contains {"control": "PCI-DSS-10.1", "reason": "Audit logging must be enabled for all actions"} if {
    input.context.audit_enabled == false
}

compliance_violations contains {"control": "HIPAA-164.312a", "reason": "Credential actions require MFA verification"} if {
    input.action in credential_actions
    not input.context.mfa_verified == true
}

# --- Rule 3: compliance_satisfied ---
# Set of control IDs whose requirements are met.

compliance_satisfied contains "SOC2-CC8.1" if {
    not input.action in read_only_actions
    input.context.approval_status == "approved"
}

compliance_satisfied contains "SOC2-CC8.1" if {
    not input.action in read_only_actions
    not input.environment == "production"
}

compliance_satisfied contains "PCI-DSS-6.2" if {
    input.action in patching_actions
}

compliance_satisfied contains "PCI-DSS-10.1" if {
    not input.context.audit_enabled == false
}

compliance_satisfied contains "HIPAA-164.312a" if {
    input.action in credential_actions
    input.context.mfa_verified == true
}

compliance_satisfied contains "SOC2-CC7.1" if {
    input.action in monitoring_actions
}

compliance_satisfied contains "CIS-5.2" if {
    input.action in k8s_pod_actions
}

# ShieldOps Action-Specific Deny Rules
# Fine-grained deny rules for specific action types and contexts.

package shieldops

import rego.v1

# Deny scale_horizontal with more than 50 replicas
deny contains msg if {
    input.action == "scale_horizontal"
    input.parameters.replicas > 50
    msg := sprintf(
        "Scale action denied: %d replicas exceeds maximum of 50",
        [input.parameters.replicas],
    )
}

# Deny restart_pod in production if too many recent restarts (loop protection)
deny contains msg if {
    input.action == "restart_pod"
    input.environment == "production"
    input.context.recent_restarts > 5
    msg := sprintf(
        "Restart loop protection: %d recent restarts exceed limit of 5",
        [input.context.recent_restarts],
    )
}

# Deny run_command containing dangerous patterns
deny contains msg if {
    input.action == "run_command"
    contains(input.parameters.command, "rm -rf /")
    msg := "Forbidden command: rm -rf /"
}

deny contains msg if {
    input.action == "run_command"
    contains(input.parameters.command, "dd if=")
    msg := "Forbidden command: dd"
}

deny contains msg if {
    input.action == "run_command"
    contains(lower(input.parameters.command), "drop table")
    msg := "Forbidden command: DROP TABLE"
}

# Deny stop_instance in production (already in forbidden_actions, belt-and-suspenders)
deny contains msg if {
    input.action == "stop_instance"
    input.environment == "production"
    msg := "Stopping instances in production is forbidden"
}

# Deny drain_node in production without approval
deny contains msg if {
    input.action == "drain_node"
    input.environment == "production"
    not input.context.approval_status == "approved"
    msg := "Draining production nodes requires explicit approval"
}

# Deny rollback_deployment in production without approval
deny contains msg if {
    input.action == "rollback_deployment"
    input.environment == "production"
    not input.context.approval_status == "approved"
    msg := "Production deployment rollbacks require explicit approval"
}

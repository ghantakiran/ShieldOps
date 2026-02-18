# ShieldOps Default OPA Policies
# These policies govern what actions agents can take in each environment.

package shieldops

import rego.v1

default allow := false

# Allow read-only actions in all environments
allow if {
    input.action in read_only_actions
}

# Allow low-risk actions in development
allow if {
    input.environment == "development"
    input.risk_level == "low"
}

# Allow low-risk actions in staging
allow if {
    input.environment == "staging"
    input.risk_level == "low"
}

# Allow medium-risk actions in development without approval
allow if {
    input.environment == "development"
    input.risk_level == "medium"
}

# Allow medium-risk actions in staging without approval
allow if {
    input.environment == "staging"
    input.risk_level == "medium"
}

# Allow low-risk actions in production for safe operations
allow if {
    input.environment == "production"
    input.risk_level == "low"
    input.action in production_safe_actions
}

# Allow medium-risk production actions for safe operations
allow if {
    input.environment == "production"
    input.risk_level == "medium"
    input.action in production_safe_actions
}

# Allow high-risk production actions only with explicit approval
allow if {
    input.environment == "production"
    input.risk_level == "high"
    input.context.approval_status == "approved"
}

# Allow critical production actions only with explicit approval
allow if {
    input.environment == "production"
    input.risk_level == "critical"
    input.context.approval_status == "approved"
}

# Read-only actions that are always allowed
read_only_actions := {
    "query_logs",
    "query_metrics",
    "query_traces",
    "get_health",
    "list_resources",
    "get_events",
    "check_compliance",
}

# Actions allowed in production without approval (low/medium risk)
production_safe_actions := {
    "restart_pod",
    "restart_service",
    "reboot_instance",
    "scale_horizontal",
    "force_new_deployment",
    "update_desired_count",
    "trigger_renewal",
}

# Actions that are NEVER allowed (hard deny)
deny contains msg if {
    input.action in forbidden_actions
    msg := sprintf("Action '%s' is forbidden by policy", [input.action])
}

forbidden_actions := {
    "delete_database",
    "drop_table",
    "delete_namespace",
    "modify_iam_root",
    "disable_logging",
    "disable_monitoring",
    "stop_instance",
}

# Blast radius check
deny contains msg if {
    input.affected_resources > max_blast_radius[input.environment]
    msg := sprintf(
        "Action affects %d resources, limit is %d for %s",
        [input.affected_resources, max_blast_radius[input.environment], input.environment],
    )
}

max_blast_radius := {
    "development": 50,
    "staging": 20,
    "production": 5,
}

# Change freeze window check
deny contains msg if {
    input.environment == "production"
    is_freeze_window
    not input.context.override_freeze
    msg := "Action blocked during change freeze window"
}

# Rate limiting: max actions per hour per environment
deny contains msg if {
    input.context.actions_this_hour > max_actions_per_hour[input.environment]
    msg := sprintf(
        "Rate limit exceeded: %d actions this hour, limit is %d",
        [input.context.actions_this_hour, max_actions_per_hour[input.environment]],
    )
}

max_actions_per_hour := {
    "development": 100,
    "staging": 50,
    "production": 20,
}

# Helper: freeze window is Saturday/Sunday (UTC)
is_freeze_window if {
    day := time.weekday(time.now_ns())
    day == "Saturday"
}

is_freeze_window if {
    day := time.weekday(time.now_ns())
    day == "Sunday"
}

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

# Helper: check if current time is in a freeze window
# TODO: Make configurable per customer
is_freeze_window if {
    false  # Placeholder — implement with actual freeze window logic
}

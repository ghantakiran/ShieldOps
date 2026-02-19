# ShieldOps Team Scoping Policies
# Per-team action scoping: ownership checks, rate limits, and environment restrictions.

package shieldops

import rego.v1

# Deny if a team tries to modify resources owned by a different team
deny contains msg if {
    input.team
    input.resource_labels.team
    input.team != input.resource_labels.team
    msg := sprintf(
        "Team '%s' cannot modify resources owned by team '%s'",
        [input.team, input.resource_labels.team],
    )
}

# Deny if team has exceeded its per-team hourly action limit
deny contains msg if {
    input.team
    count := input.context.team_actions_this_hour
    limit := team_hourly_limits[input.environment]
    count > limit
    msg := sprintf(
        "Team '%s' rate limit exceeded: %d actions this hour, limit is %d for %s",
        [input.team, count, limit, input.environment],
    )
}

team_hourly_limits := {
    "development": 50,
    "staging": 25,
    "production": 10,
}

# Deny if team is restricted from accessing certain environment scopes
deny contains msg if {
    input.team
    restricted := team_environment_restrictions[input.team]
    input.resource_labels.scope in restricted
    msg := sprintf(
        "Team '%s' is restricted from scope '%s'",
        [input.team, input.resource_labels.scope],
    )
}

team_environment_restrictions := {
    "frontend": {"production_database", "production_infrastructure"},
    "mobile": {"production_database", "production_infrastructure"},
    "data": {"production_infrastructure"},
}

# ShieldOps Extended Rate Limiting Rules
# Per-minute burst limits and per-team hourly limits.

package shieldops

import rego.v1

# Per-minute burst limits
deny contains msg if {
    input.context.actions_this_minute > burst_limits_per_minute[input.environment]
    msg := sprintf(
        "Burst rate limit exceeded: %d actions this minute, limit is %d for %s",
        [input.context.actions_this_minute, burst_limits_per_minute[input.environment], input.environment],
    )
}

burst_limits_per_minute := {
    "development": 10,
    "staging": 5,
    "production": 3,
}

# Per-team hourly limits
deny contains msg if {
    input.context.team_actions_this_hour > team_hourly_limits[input.environment]
    msg := sprintf(
        "Team rate limit exceeded: %d actions this hour for team '%s', limit is %d for %s",
        [input.context.team_actions_this_hour, input.team, team_hourly_limits[input.environment], input.environment],
    )
}

team_hourly_limits := {
    "development": 50,
    "staging": 25,
    "production": 10,
}

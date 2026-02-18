"""Dashboard configuration — colors, API settings, and defaults."""

import os

# --- API Connection ---
API_BASE_URL = os.getenv("SHIELDOPS_API_URL", "http://localhost:8000/api/v1")
API_TIMEOUT = int(os.getenv("SHIELDOPS_DASHBOARD_TIMEOUT", "10"))

# --- Display defaults ---
DEFAULT_PAGE_SIZE = 25
AUTO_REFRESH_INTERVAL = 10  # seconds
SUPPORTED_ENVIRONMENTS = ["production", "staging", "development"]

# --- Color palettes ---

STATUS_COLORS: dict[str, str] = {
    "idle": "#6B7280",
    "investigating": "#3B82F6",
    "remediating": "#F59E0B",
    "waiting_approval": "#8B5CF6",
    "error": "#EF4444",
    "disabled": "#9CA3AF",
    # Execution statuses
    "pending": "#F59E0B",
    "in_progress": "#3B82F6",
    "success": "#10B981",
    "failed": "#EF4444",
    "rolled_back": "#8B5CF6",
    "cancelled": "#6B7280",
    # Approval statuses
    "approved": "#10B981",
    "denied": "#EF4444",
    "timeout": "#F59E0B",
    "escalated": "#8B5CF6",
    # Generic
    "complete": "#10B981",
    "active": "#3B82F6",
    "unknown": "#6B7280",
}

RISK_COLORS: dict[str, str] = {
    "low": "#10B981",
    "medium": "#F59E0B",
    "high": "#F97316",
    "critical": "#EF4444",
}

SEVERITY_COLORS: dict[str, str] = {
    "info": "#6B7280",
    "low": "#10B981",
    "warning": "#F59E0B",
    "medium": "#F59E0B",
    "high": "#F97316",
    "critical": "#EF4444",
}

CONFIDENCE_COLORS: dict[str, str] = {
    "high": "#10B981",  # >= 0.8
    "medium": "#F59E0B",  # >= 0.5
    "low": "#EF4444",  # < 0.5
}


def confidence_color(value: float) -> str:
    """Return color for a confidence value 0.0-1.0."""
    if value >= 0.8:
        return CONFIDENCE_COLORS["high"]
    if value >= 0.5:
        return CONFIDENCE_COLORS["medium"]
    return CONFIDENCE_COLORS["low"]

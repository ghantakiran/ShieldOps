"""Reusable UI components for the ShieldOps dashboard."""

from __future__ import annotations

import json
import time
from typing import Any

import streamlit as st

from shieldops.dashboard.config import (
    AUTO_REFRESH_INTERVAL,
    RISK_COLORS,
    SEVERITY_COLORS,
    STATUS_COLORS,
    confidence_color,
)

# ------------------------------------------------------------------
# Badges
# ------------------------------------------------------------------


def render_status_badge(status: str) -> str:
    """Return an HTML span styled as a status badge."""
    color = STATUS_COLORS.get(status, STATUS_COLORS["unknown"])
    label = status.replace("_", " ").title()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.85em;font-weight:600">{label}</span>'
    )


def render_risk_badge(risk: str) -> str:
    """Return an HTML span styled as a risk-level badge."""
    color = RISK_COLORS.get(risk, "#6B7280")
    label = risk.upper()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.85em;font-weight:600">{label}</span>'
    )


def render_severity_badge(severity: str) -> str:
    """Return an HTML span styled as a severity badge."""
    color = SEVERITY_COLORS.get(severity, "#6B7280")
    label = severity.upper()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.85em;font-weight:600">{label}</span>'
    )


# ------------------------------------------------------------------
# Metric cards
# ------------------------------------------------------------------


def render_metric_card(label: str, value: Any, delta: str | None = None) -> None:
    """Display a single metric using st.metric."""
    st.metric(label=label, value=value, delta=delta)


def render_metric_row(metrics: list[tuple[str, Any, str | None]]) -> None:
    """Render a row of metric cards in equal-width columns.

    Each tuple is (label, value, delta_or_None).
    """
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics, strict=False):
        with col:
            st.metric(label=label, value=value, delta=delta)


# ------------------------------------------------------------------
# Reasoning chain
# ------------------------------------------------------------------


def render_reasoning_chain(steps: list[dict]) -> None:
    """Display a reasoning chain as a vertical timeline."""
    if not steps:
        st.info("No reasoning steps recorded.")
        return
    for i, step in enumerate(steps, 1):
        node = step.get("node", step.get("step", f"Step {i}"))
        summary = step.get("summary", step.get("description", ""))
        duration = step.get("duration_ms")
        icon = _node_icon(node)
        dur_label = f"  ({duration}ms)" if duration else ""
        st.markdown(f"**{icon} {i}. {node}**{dur_label}")
        if summary:
            st.caption(summary)


def _node_icon(node: str) -> str:
    icons: dict[str, str] = {
        "classify": "🏷",
        "gather_logs": "📋",
        "analyze_metrics": "📊",
        "trace_analysis": "🔍",
        "correlate": "🔗",
        "hypothesize": "💡",
        "validate": "✅",
        "plan": "📝",
        "evaluate_policy": "🛡",
        "execute": "⚡",
        "verify": "✅",
        "snapshot": "📸",
    }
    for key, icon in icons.items():
        if key in node.lower():
            return icon
    return "▶"


# ------------------------------------------------------------------
# Confidence bar
# ------------------------------------------------------------------


def render_confidence_bar(label: str, value: float) -> None:
    """Render a labeled progress bar with colored confidence value."""
    color = confidence_color(value)
    pct = int(value * 100)
    st.markdown(
        f'{label}: <span style="color:{color};font-weight:700">{pct}%</span>',
        unsafe_allow_html=True,
    )
    st.progress(value)


# ------------------------------------------------------------------
# Data table
# ------------------------------------------------------------------


def render_data_table(
    rows: list[dict],
    columns: list[str] | None = None,
    key: str | None = None,
) -> None:
    """Render rows as a Streamlit dataframe.

    If *columns* is provided, only those keys are shown (in order).
    """
    if not rows:
        render_empty_state("No data available")
        return
    if columns:
        rows = [{c: r.get(c, "") for c in columns} for r in rows]
    st.dataframe(rows, use_container_width=True, key=key)


# ------------------------------------------------------------------
# Page header & empty state
# ------------------------------------------------------------------


def render_page_header(title: str, description: str = "") -> None:
    """Render a page title and optional description."""
    st.title(title)
    if description:
        st.caption(description)
    st.divider()


def render_empty_state(message: str = "Nothing to display") -> None:
    """Render a centered empty-state placeholder."""
    st.info(message)


# ------------------------------------------------------------------
# Auto-refresh
# ------------------------------------------------------------------


def render_auto_refresh(sidebar: bool = True) -> None:
    """Add an auto-refresh toggle to the sidebar.

    When enabled, the page re-runs every ``AUTO_REFRESH_INTERVAL`` seconds.
    """
    container = st.sidebar if sidebar else st
    enabled = container.toggle("Auto-refresh", value=False, key="auto_refresh_toggle")
    if enabled:
        interval = container.slider(
            "Interval (s)",
            min_value=5,
            max_value=60,
            value=AUTO_REFRESH_INTERVAL,
            key="auto_refresh_interval",
        )
        time.sleep(interval)
        st.rerun()


# ------------------------------------------------------------------
# JSON expander
# ------------------------------------------------------------------


def render_json_expander(label: str, data: Any, expanded: bool = False) -> None:
    """Show a collapsible JSON viewer."""
    with st.expander(label, expanded=expanded):
        st.json(data if isinstance(data, (dict, list)) else json.loads(str(data)))

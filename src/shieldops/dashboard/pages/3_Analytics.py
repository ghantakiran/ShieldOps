"""Analytics page — MTTR trends, resolution rate, agent accuracy, cost savings."""

import plotly.graph_objects as go
import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_empty_state,
    render_metric_row,
    render_page_header,
)

st.set_page_config(page_title="Analytics | ShieldOps", page_icon="📊", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Analytics", "Operational metrics and performance trends")
render_auto_refresh()

# --- Period selector ---
period = st.selectbox("Period", ["7d", "14d", "30d", "90d"], index=2, key="analytics_period")

# --- Fetch data ---
mttr = client.get_mttr_trends(period=period)
resolution = client.get_resolution_rate(period=period)
accuracy = client.get_agent_accuracy(period=period)
savings = client.get_cost_savings_analytics(period=period)

# --- KPI row ---
render_metric_row(
    [
        ("Current MTTR", f"{mttr.get('current_mttr_minutes', 0):.0f} min", None),
        ("Automated Resolution", f"{resolution.get('automated_rate', 0) * 100:.0f}%", None),
        ("Agent Accuracy", f"{accuracy.get('accuracy', 0) * 100:.0f}%", None),
        ("Hours Saved", f"{savings.get('hours_saved', 0):.0f}h", None),
    ]
)

st.divider()

# --- Charts ---
col_left, col_right = st.columns(2)

with col_left:
    # MTTR trend line chart
    st.markdown("#### MTTR Trend")
    data_points = mttr.get("data_points", [])
    if data_points:
        dates = [p.get("date", p.get("timestamp", "")) for p in data_points]
        values = [p.get("mttr_minutes", p.get("value", 0)) for p in data_points]
        fig = go.Figure(
            go.Scatter(
                x=dates,
                y=values,
                mode="lines+markers",
                line={"color": "#3B82F6", "width": 2},
                marker={"size": 6},
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=300,
            margin={"l": 40, "r": 20, "t": 20, "b": 40},
            xaxis_title="Date",
            yaxis_title="Minutes",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        render_empty_state("No MTTR data points for this period")

with col_right:
    # Resolution rate donut chart
    st.markdown("#### Resolution Rate")
    auto_rate = resolution.get("automated_rate", 0)
    manual_rate = resolution.get("manual_rate", 0)
    total_incidents = resolution.get("total_incidents", 0)

    if total_incidents > 0:
        fig = go.Figure(
            go.Pie(
                labels=["Automated", "Manual"],
                values=[auto_rate, manual_rate],
                hole=0.5,
                marker={"colors": ["#10B981", "#6B7280"]},
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=300,
            margin={"l": 20, "r": 20, "t": 20, "b": 20},
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Total incidents: {total_incidents}")
    else:
        render_empty_state("No resolution data for this period")

st.divider()

col_acc, col_sav = st.columns(2)

with col_acc:
    # Agent accuracy gauge
    st.markdown("#### Agent Accuracy")
    acc_val = accuracy.get("accuracy", 0)
    total_inv = accuracy.get("total_investigations", 0)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=acc_val * 100,
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#3B82F6"},
                "steps": [
                    {"range": [0, 50], "color": "rgba(239,68,68,0.19)"},
                    {"range": [50, 80], "color": "rgba(245,158,11,0.19)"},
                    {"range": [80, 100], "color": "rgba(16,185,129,0.19)"},
                ],
            },
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=250,
        margin={"l": 20, "r": 20, "t": 30, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Based on {total_inv} investigations")

with col_sav:
    # Cost savings summary
    st.markdown("#### Cost Savings")
    hours = savings.get("hours_saved", 0)
    usd = savings.get("estimated_savings_usd", 0)
    rate = savings.get("engineer_hourly_rate", 75)

    render_metric_row(
        [
            ("Hours Saved", f"{hours:.0f}h", None),
            ("Estimated Savings", f"${usd:,.0f}", None),
        ]
    )
    st.caption(f"Based on ${rate}/hr engineer rate")

"""Cost Intelligence page — anomalies, optimizations, and savings."""

import streamlit as st
import plotly.graph_objects as go

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_data_table,
    render_empty_state,
    render_metric_row,
    render_page_header,
    render_severity_badge,
)
from shieldops.dashboard.config import SUPPORTED_ENVIRONMENTS

st.set_page_config(page_title="Cost Intelligence | ShieldOps", page_icon="💰", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Cost Intelligence", "Cost anomaly detection, optimization, and savings tracking")
render_auto_refresh()

# --- Savings KPIs ---
savings = client.get_savings_summary()

if "error" in savings:
    st.error(savings["error"])
else:
    render_metric_row([
        ("Monthly Spend", f"${savings.get('total_monthly_spend', 0):,.0f}", None),
        ("Potential Savings", f"${savings.get('total_potential_savings', 0):,.0f}", None),
        ("Hours Saved (Automation)", f"{savings.get('hours_saved_by_automation', 0):.0f}h", None),
        ("Automation Savings", f"${savings.get('automation_savings_usd', 0):,.0f}", None),
    ])

st.divider()

# --- Tabs ---
tab_anomalies, tab_opts, tab_savings, tab_trigger = st.tabs([
    "Anomalies", "Optimizations", "Savings Breakdown", "Run Analysis",
])

# --- Anomalies ---
with tab_anomalies:
    anomaly_data = client.list_anomalies()
    if "error" in anomaly_data:
        st.error(anomaly_data["error"])
    else:
        anomalies = anomaly_data.get("anomalies", [])
        if anomalies:
            render_data_table(
                anomalies,
                columns=["service", "resource", "severity", "expected_cost",
                         "actual_cost", "deviation_pct", "detected_at"],
            )
        else:
            render_empty_state("No cost anomalies detected. Run a cost analysis to begin.")

# --- Optimizations ---
with tab_opts:
    opt_data = client.list_optimizations()
    if "error" in opt_data:
        st.error(opt_data["error"])
    else:
        optimizations = opt_data.get("optimizations", [])
        total_potential = opt_data.get("total_potential_savings", 0)

        if optimizations:
            st.markdown(f"**Total potential savings:** ${total_potential:,.0f}/month")
            st.divider()

            # Savings-by-category bar chart
            categories: dict[str, float] = {}
            for opt in optimizations:
                cat = opt.get("category", "Other")
                categories[cat] = categories.get(cat, 0) + opt.get("estimated_savings", 0)

            if categories:
                fig = go.Figure(go.Bar(
                    x=list(categories.keys()),
                    y=list(categories.values()),
                    marker_color="#10B981",
                ))
                fig.update_layout(
                    template="plotly_dark",
                    height=300,
                    margin={"l": 40, "r": 20, "t": 20, "b": 40},
                    xaxis_title="Category",
                    yaxis_title="Potential Savings ($)",
                )
                st.plotly_chart(fig, use_container_width=True)

            # Recommendation cards
            for opt in optimizations:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{opt.get('title', opt.get('recommendation', ''))}**")
                        st.caption(opt.get("description", ""))
                    with col2:
                        st.markdown(f"${opt.get('estimated_savings', 0):,.0f}/mo")
                    with col3:
                        st.markdown(
                            render_severity_badge(opt.get("priority", opt.get("impact", "medium"))),
                            unsafe_allow_html=True,
                        )
                    st.divider()
        else:
            render_empty_state("No optimization recommendations yet.")

# --- Savings breakdown ---
with tab_savings:
    if "error" not in savings and savings.get("total_monthly_spend", 0) > 0:
        spend = savings.get("total_monthly_spend", 1)
        potential = savings.get("total_potential_savings", 0)
        auto = savings.get("automation_savings_usd", 0)

        fig = go.Figure(go.Pie(
            labels=["Current Spend (after savings)", "Potential Savings", "Automation Savings"],
            values=[max(spend - potential - auto, 0), potential, auto],
            hole=0.4,
            marker={"colors": ["#6B7280", "#F59E0B", "#10B981"]},
        ))
        fig.update_layout(
            template="plotly_dark",
            height=350,
            margin={"l": 20, "r": 20, "t": 20, "b": 20},
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        render_empty_state("No savings data. Run a cost analysis to generate insights.")

# --- Trigger analysis ---
with tab_trigger:
    with st.form("trigger_cost_analysis"):
        st.markdown("#### Run Cost Analysis")
        environment = st.selectbox("Environment", SUPPORTED_ENVIRONMENTS, key="cost_env")
        analysis_type = st.selectbox(
            "Analysis Type",
            ["full", "anomaly_only", "optimization_only", "savings_only"],
        )
        target_services = st.text_input(
            "Target Services (comma-separated)",
            placeholder="ec2, rds, s3",
        )
        period = st.selectbox("Period", ["7d", "14d", "30d", "90d"], index=2)

        if st.form_submit_button("Start Analysis"):
            targets = [t.strip() for t in target_services.split(",") if t.strip()]
            result = client.trigger_cost_analysis(
                environment=environment,
                analysis_type=analysis_type,
                target_services=targets or None,
                period=period,
            )
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(f"Analysis triggered: {result.get('message', 'OK')}")

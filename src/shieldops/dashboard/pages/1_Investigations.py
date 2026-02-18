"""Investigations page — list, detail, and trigger investigations."""

import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_confidence_bar,
    render_data_table,
    render_empty_state,
    render_json_expander,
    render_page_header,
    render_reasoning_chain,
    render_status_badge,
)

st.set_page_config(page_title="Investigations | ShieldOps", page_icon="🔍", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Investigations", "Root cause analysis powered by the Investigation Agent")
render_auto_refresh()

# ------------------------------------------------------------------
# Navigation: list vs detail
# ------------------------------------------------------------------

if "selected_investigation" not in st.session_state:
    st.session_state.selected_investigation = None


def show_detail(inv_id: str) -> None:
    st.session_state.selected_investigation = inv_id


def back_to_list() -> None:
    st.session_state.selected_investigation = None


# ------------------------------------------------------------------
# Detail view
# ------------------------------------------------------------------

if st.session_state.selected_investigation:
    st.button("← Back to list", on_click=back_to_list)

    detail = client.get_investigation(st.session_state.selected_investigation)
    if "error" in detail:
        st.error(detail["error"])
    else:
        # Header
        col_l, col_r = st.columns([3, 1])
        with col_l:
            st.subheader(detail.get("alert_name", detail.get("alert_id", "")))
            st.markdown(
                render_status_badge(detail.get("status", "unknown")),
                unsafe_allow_html=True,
            )
        with col_r:
            conf = detail.get("confidence", 0)
            render_confidence_bar("Confidence", conf)

        st.divider()

        # Two-column layout: reasoning chain + evidence
        left, right = st.columns(2)

        with left:
            st.markdown("#### Reasoning Chain")
            render_reasoning_chain(detail.get("reasoning_steps", []))

        with right:
            st.markdown("#### Evidence")
            tab_logs, tab_metrics, tab_traces = st.tabs(["Logs", "Metrics", "Traces"])
            with tab_logs:
                logs = detail.get("log_findings", [])
                if logs:
                    render_data_table(logs)
                else:
                    render_empty_state("No log findings")
            with tab_metrics:
                metrics = detail.get("metric_anomalies", [])
                if metrics:
                    render_data_table(metrics)
                else:
                    render_empty_state("No metric anomalies")
            with tab_traces:
                traces = detail.get("trace_results", [])
                if traces:
                    render_data_table(traces)
                else:
                    render_empty_state("No trace results")

        # Hypotheses
        st.divider()
        st.markdown("#### Hypotheses")
        hypotheses = detail.get("hypotheses", [])
        if hypotheses:
            for h in hypotheses:
                with st.container():
                    render_confidence_bar(
                        h.get("description", h.get("hypothesis", "Unknown")),
                        h.get("confidence", 0),
                    )
                    if h.get("evidence"):
                        st.caption(f"Evidence: {', '.join(h['evidence'])}")
        else:
            render_empty_state("No hypotheses generated")

        render_json_expander("Raw investigation data", detail)

# ------------------------------------------------------------------
# List view
# ------------------------------------------------------------------

else:
    # Filters
    col_filter, col_trigger = st.columns([3, 1])
    with col_filter:
        status_filter = st.selectbox(
            "Status",
            ["All", "in_progress", "complete", "failed"],
            key="inv_status_filter",
        )
    with col_trigger:
        st.markdown("")  # spacer
        trigger_btn = st.button("+ New Investigation")

    selected_status = None if status_filter == "All" else status_filter
    data = client.list_investigations(status=selected_status)

    if "error" in data:
        st.error(data["error"])
    else:
        investigations = data.get("investigations", [])
        if investigations:
            for inv in investigations:
                inv_id = inv.get("investigation_id", "")
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.markdown(f"**{inv.get('alert_name', inv_id)}**  \n`{inv_id}`")
                with col2:
                    st.markdown(
                        render_status_badge(inv.get("status", "unknown")),
                        unsafe_allow_html=True,
                    )
                with col3:
                    conf = inv.get("confidence", 0)
                    st.markdown(f"**{int(conf * 100)}%** conf.")
                with col4:
                    st.button("View", key=f"view_{inv_id}", on_click=show_detail, args=(inv_id,))
                st.divider()
        else:
            render_empty_state("No investigations found. Trigger one below or from Supervisor.")

    # Trigger form
    if trigger_btn:
        with st.form("trigger_investigation"):
            st.markdown("#### Trigger New Investigation")
            alert_id = st.text_input("Alert ID", placeholder="alert-12345")
            alert_name = st.text_input("Alert Name", placeholder="HighCPUUsage")
            severity = st.selectbox("Severity", ["critical", "warning", "info"])
            source = st.text_input("Source", value="dashboard")
            description = st.text_area("Description", placeholder="Optional context...")

            if st.form_submit_button("Submit"):
                if alert_id and alert_name:
                    result = client.trigger_investigation(
                        alert_id=alert_id,
                        alert_name=alert_name,
                        severity=severity,
                        source=source,
                        description=description or None,
                    )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"Investigation triggered: {result.get('message', 'OK')}")
                else:
                    st.warning("Alert ID and Alert Name are required.")

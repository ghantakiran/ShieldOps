"""Learning page — patterns, playbook updates, threshold adjustments."""

import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_data_table,
    render_empty_state,
    render_metric_row,
    render_page_header,
)

st.set_page_config(page_title="Learning | ShieldOps", page_icon="🧠", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Learning", "Continuous improvement — patterns, playbooks, and thresholds")
render_auto_refresh()

# --- Improvement KPIs ---
patterns_data = client.list_patterns()
playbook_data = client.list_playbook_updates()
threshold_data = client.list_threshold_adjustments()

total_patterns = patterns_data.get("total", 0)
total_playbooks = playbook_data.get("total", 0)
total_thresholds = threshold_data.get("total", 0)
fp_reduction = threshold_data.get("estimated_fp_reduction", 0)

render_metric_row([
    ("Patterns Discovered", total_patterns, None),
    ("Playbook Updates", total_playbooks, None),
    ("Threshold Adjustments", total_thresholds, None),
    ("Est. FP Reduction", f"{fp_reduction * 100:.0f}%" if fp_reduction <= 1 else f"{fp_reduction}%",
     None),
])

st.divider()

tab_patterns, tab_playbooks, tab_thresholds, tab_trigger = st.tabs([
    "Pattern Insights", "Playbook Updates", "Threshold Adjustments", "Trigger Cycle",
])

# --- Patterns ---
with tab_patterns:
    if "error" in patterns_data:
        st.error(patterns_data["error"])
    else:
        patterns = patterns_data.get("patterns", [])
        if patterns:
            render_data_table(
                patterns,
                columns=["alert_type", "pattern", "frequency", "confidence",
                         "recommended_action", "occurrences"],
            )
        else:
            render_empty_state("No patterns found. Run a learning cycle to discover patterns.")

# --- Playbook updates ---
with tab_playbooks:
    if "error" in playbook_data:
        st.error(playbook_data["error"])
    else:
        updates = playbook_data.get("playbook_updates", [])
        if updates:
            for upd in updates:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{upd.get('playbook_name', upd.get('title', 'Unnamed'))}**")
                        st.caption(upd.get("description", upd.get("change_summary", "")))
                    with col2:
                        utype = upd.get("update_type", "update")
                        st.markdown(f"`{utype}`")
                    if upd.get("diff"):
                        with st.expander("View diff"):
                            st.code(upd["diff"], language="diff")
                    st.divider()
        else:
            render_empty_state("No playbook updates recommended.")

# --- Threshold adjustments ---
with tab_thresholds:
    if "error" in threshold_data:
        st.error(threshold_data["error"])
    else:
        adjustments = threshold_data.get("threshold_adjustments", [])
        if adjustments:
            render_data_table(
                adjustments,
                columns=["metric_name", "current_threshold", "recommended_threshold",
                         "alert_type", "false_positive_rate", "estimated_fp_reduction"],
            )
        else:
            render_empty_state("No threshold adjustments recommended.")

# --- Trigger cycle ---
with tab_trigger:
    with st.form("trigger_learning"):
        st.markdown("#### Trigger Learning Cycle")
        learning_type = st.selectbox(
            "Learning Type",
            ["full", "pattern_only", "playbook_only", "threshold_only"],
        )
        period = st.selectbox("Period", ["7d", "14d", "30d", "90d"], index=2)

        if st.form_submit_button("Start Cycle"):
            result = client.trigger_learning_cycle(
                learning_type=learning_type,
                period=period,
            )
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(f"Learning cycle triggered: {result.get('message', 'OK')}")

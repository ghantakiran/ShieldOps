"""Remediations page — timeline, approve/deny/rollback, and trigger."""

import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_data_table,
    render_empty_state,
    render_json_expander,
    render_page_header,
    render_reasoning_chain,
    render_risk_badge,
    render_status_badge,
)
from shieldops.dashboard.config import SUPPORTED_ENVIRONMENTS

st.set_page_config(page_title="Remediations | ShieldOps", page_icon="🔧", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Remediations", "Remediation actions with policy gates and rollback")
render_auto_refresh()

# ------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------

if "selected_remediation" not in st.session_state:
    st.session_state.selected_remediation = None


def show_detail(rem_id: str) -> None:
    st.session_state.selected_remediation = rem_id


def back_to_list() -> None:
    st.session_state.selected_remediation = None


# ------------------------------------------------------------------
# Detail view
# ------------------------------------------------------------------

if st.session_state.selected_remediation:
    st.button("← Back to list", on_click=back_to_list)

    detail = client.get_remediation(st.session_state.selected_remediation)
    if "error" in detail:
        st.error(detail["error"])
    else:
        # Header row
        col_l, col_r = st.columns([3, 1])
        with col_l:
            action = detail.get("action_type", "")
            target = detail.get("target_resource", "")
            st.subheader(f"{action} → {target}")
            badges = " ".join(
                [
                    render_status_badge(detail.get("status", "unknown")),
                    render_risk_badge(detail.get("risk_level", "medium")),
                ]
            )
            st.markdown(badges, unsafe_allow_html=True)
        with col_r:
            env = detail.get("environment", "")
            st.markdown(f"**Environment:** {env}")

        # Action buttons
        status = detail.get("status", "")
        if status in ("pending", "waiting_approval"):
            st.divider()
            col_a, col_d = st.columns(2)
            with col_a:
                if st.button("Approve", type="primary"):
                    res = client.approve_remediation(
                        st.session_state.selected_remediation,
                        approver="dashboard-user",
                    )
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        st.success("Approved")
                        st.rerun()
            with col_d:
                reason = st.text_input("Denial reason", key="deny_reason")
                if st.button("Deny"):
                    res = client.deny_remediation(
                        st.session_state.selected_remediation,
                        approver="dashboard-user",
                        reason=reason,
                    )
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        st.warning("Denied")
                        st.rerun()

        if status in ("success", "complete") and st.button("Rollback"):
            res = client.rollback_remediation(st.session_state.selected_remediation)
            if "error" in res:
                st.error(res["error"])
            else:
                st.info(f"Rollback initiated (snapshot: {res.get('snapshot_id', 'N/A')})")
                st.rerun()

        st.divider()

        # Detail sections
        tab_policy, tab_exec, tab_reason = st.tabs(
            [
                "Policy Evaluation",
                "Execution Result",
                "Reasoning",
            ]
        )

        with tab_policy:
            policy = detail.get("policy_evaluation", detail.get("policy_result", {}))
            if policy:
                st.json(policy)
            else:
                render_empty_state("No policy evaluation recorded")

        with tab_exec:
            result = detail.get("execution_result", detail.get("action_result", {}))
            if result:
                st.json(result)
            else:
                render_empty_state("No execution result yet")

            validation = detail.get("validation_checks", [])
            if validation:
                st.markdown("**Validation Checks**")
                render_data_table(validation)

        with tab_reason:
            render_reasoning_chain(detail.get("reasoning_steps", []))

        render_json_expander("Raw remediation data", detail)

# ------------------------------------------------------------------
# List view
# ------------------------------------------------------------------

else:
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        env_filter = st.selectbox(
            "Environment",
            ["All"] + SUPPORTED_ENVIRONMENTS,
            key="rem_env_filter",
        )
    with col2:
        status_filter = st.selectbox(
            "Status",
            [
                "All",
                "pending",
                "waiting_approval",
                "in_progress",
                "success",
                "failed",
                "rolled_back",
                "cancelled",
            ],
            key="rem_status_filter",
        )
    with col3:
        st.markdown("")
        trigger_btn = st.button("+ New Remediation")

    sel_env = None if env_filter == "All" else env_filter
    sel_status = None if status_filter == "All" else status_filter

    data = client.list_remediations(environment=sel_env, status=sel_status)

    if "error" in data:
        st.error(data["error"])
    else:
        remediations = data.get("remediations", [])
        if remediations:
            for rem in remediations:
                rem_id = rem.get("remediation_id", rem.get("id", ""))
                c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
                with c1:
                    st.markdown(f"**{rem.get('action_type', '')}**  \n`{rem_id}`")
                with c2:
                    st.markdown(f"{rem.get('target_resource', '')}")
                with c3:
                    st.markdown(
                        render_status_badge(rem.get("status", "unknown")),
                        unsafe_allow_html=True,
                    )
                with c4:
                    st.markdown(
                        render_risk_badge(rem.get("risk_level", "medium")),
                        unsafe_allow_html=True,
                    )
                with c5:
                    st.button(
                        "View", key=f"view_rem_{rem_id}", on_click=show_detail, args=(rem_id,)
                    )
                st.divider()
        else:
            render_empty_state("No remediations found.")

    # Trigger form
    if trigger_btn:
        with st.form("trigger_remediation"):
            st.markdown("#### Trigger New Remediation")
            action_type = st.selectbox(
                "Action Type",
                [
                    "restart_pod",
                    "scale_horizontal",
                    "rollback",
                    "patch",
                    "restart_service",
                    "resize",
                    "drain_node",
                ],
            )
            target = st.text_input("Target Resource", placeholder="my-app-pod-xyz")
            environment = st.selectbox("Environment", SUPPORTED_ENVIRONMENTS)
            risk_level = st.selectbox("Risk Level", ["low", "medium", "high", "critical"])
            description = st.text_area("Description", placeholder="Why this remediation?")

            if st.form_submit_button("Submit"):
                if target:
                    result = client.trigger_remediation(
                        action_type=action_type,
                        target_resource=target,
                        environment=environment,
                        risk_level=risk_level,
                        description=description,
                    )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"Remediation triggered: {result.get('message', 'OK')}")
                else:
                    st.warning("Target Resource is required.")

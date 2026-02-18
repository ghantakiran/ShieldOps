"""Supervisor page — sessions, delegated tasks, chains, escalations."""

import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_data_table,
    render_empty_state,
    render_json_expander,
    render_page_header,
    render_reasoning_chain,
    render_severity_badge,
    render_status_badge,
)

st.set_page_config(page_title="Supervisor | ShieldOps", page_icon="🎯", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Supervisor", "Orchestration sessions, delegation, and escalations")
render_auto_refresh()

# ------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------

if "selected_session" not in st.session_state:
    st.session_state.selected_session = None


def show_detail(session_id: str) -> None:
    st.session_state.selected_session = session_id


def back_to_list() -> None:
    st.session_state.selected_session = None


# ------------------------------------------------------------------
# Detail view
# ------------------------------------------------------------------

if st.session_state.selected_session:
    st.button("← Back to list", on_click=back_to_list)

    detail = client.get_session(st.session_state.selected_session)
    if "error" in detail:
        st.error(detail["error"])
    else:
        # Header
        col_l, col_r = st.columns([3, 1])
        with col_l:
            event_type = detail.get("event_type", detail.get("type", "unknown"))
            st.subheader(f"Session: {st.session_state.selected_session}")
            badges = " ".join(
                [
                    render_status_badge(detail.get("status", "unknown")),
                    render_severity_badge(detail.get("severity", "medium")),
                ]
            )
            st.markdown(badges, unsafe_allow_html=True)
        with col_r:
            st.markdown(f"**Event type:** `{event_type}`")
            st.markdown(f"**Source:** {detail.get('source', 'N/A')}")

        # Classification
        classification = detail.get("classification", {})
        if classification:
            st.divider()
            st.markdown("#### Classification")
            st.json(classification)

        st.divider()

        tab_tasks, tab_chains, tab_esc, tab_reason = st.tabs(
            [
                "Delegated Tasks",
                "Chained Workflows",
                "Escalations",
                "Reasoning",
            ]
        )

        # Delegated tasks
        with tab_tasks:
            tasks_data = client.get_session_tasks(st.session_state.selected_session)
            if "error" in tasks_data:
                st.error(tasks_data["error"])
            else:
                tasks = tasks_data.get("tasks", [])
                if tasks:
                    render_data_table(
                        tasks,
                        columns=[
                            "task_id",
                            "agent_type",
                            "action",
                            "status",
                            "result_summary",
                            "duration_ms",
                        ],
                    )
                else:
                    render_empty_state("No delegated tasks")

        # Chained workflows
        with tab_chains:
            chains = detail.get("chained_workflows", detail.get("workflow_chain", []))
            if chains:
                for i, chain in enumerate(chains, 1):
                    st.markdown(
                        f"**{i}. {chain.get('workflow', chain.get('agent', 'Unknown'))}** "
                        f"→ {render_status_badge(chain.get('status', 'unknown'))}",
                        unsafe_allow_html=True,
                    )
                    if chain.get("output_summary"):
                        st.caption(chain["output_summary"])
            else:
                render_empty_state("No chained workflows")

        # Escalations
        with tab_esc:
            esc_data = client.get_session_escalations(st.session_state.selected_session)
            if "error" in esc_data:
                st.error(esc_data["error"])
            else:
                escalations = esc_data.get("escalations", [])
                if escalations:
                    render_data_table(
                        escalations,
                        columns=[
                            "escalation_id",
                            "reason",
                            "severity",
                            "target",
                            "status",
                            "created_at",
                        ],
                    )
                else:
                    render_empty_state("No escalations")

        # Reasoning
        with tab_reason:
            render_reasoning_chain(detail.get("reasoning_steps", []))

        render_json_expander("Raw session data", detail)

# ------------------------------------------------------------------
# List view
# ------------------------------------------------------------------

else:
    col_filter, col_submit = st.columns([3, 1])
    with col_filter:
        event_filter = st.selectbox(
            "Event Type",
            [
                "All",
                "alert",
                "incident",
                "cve_alert",
                "remediation_request",
                "security_event",
                "cost_anomaly",
            ],
            key="sup_event_filter",
        )
    with col_submit:
        st.markdown("")
        submit_btn = st.button("+ Submit Event")

    sel_type = None if event_filter == "All" else event_filter
    data = client.list_sessions(event_type=sel_type)

    if "error" in data:
        st.error(data["error"])
    else:
        sessions = data.get("sessions", [])
        if sessions:
            for sess in sessions:
                sid = sess.get("session_id", "")
                c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
                with c1:
                    st.markdown(f"**{sess.get('event_type', 'unknown')}**  \n`{sid}`")
                with c2:
                    desc = sess.get("description", sess.get("summary", ""))
                    st.markdown(desc[:80] if desc else "—")
                with c3:
                    st.markdown(
                        render_severity_badge(sess.get("severity", "medium")),
                        unsafe_allow_html=True,
                    )
                with c4:
                    st.markdown(
                        render_status_badge(sess.get("status", "unknown")),
                        unsafe_allow_html=True,
                    )
                with c5:
                    st.button(
                        "View",
                        key=f"view_sess_{sid}",
                        on_click=show_detail,
                        args=(sid,),
                    )
                st.divider()
        else:
            render_empty_state("No supervisor sessions yet.")

    # Submit event form
    if submit_btn:
        with st.form("submit_event"):
            st.markdown("#### Submit Event to Supervisor")
            event_type = st.selectbox(
                "Event Type",
                [
                    "alert",
                    "incident",
                    "cve_alert",
                    "remediation_request",
                    "security_event",
                    "cost_anomaly",
                ],
                key="submit_event_type",
            )
            severity = st.selectbox("Severity", ["critical", "high", "medium", "low"])
            source = st.text_input("Source", value="dashboard")
            resource_id = st.text_input("Resource ID", placeholder="pod/my-app-xyz")
            description = st.text_area("Description", placeholder="Event context...")

            if st.form_submit_button("Submit"):
                result = client.submit_event(
                    event_type=event_type,
                    severity=severity,
                    source=source,
                    resource_id=resource_id or None,
                    description=description or None,
                )
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(f"Event submitted: {result.get('message', 'OK')}")

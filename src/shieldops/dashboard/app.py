"""ShieldOps Dashboard — Fleet Overview (home page).

Launch:
    streamlit run src/shieldops/dashboard/app.py
"""

import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_data_table,
    render_empty_state,
    render_metric_row,
    render_page_header,
    render_status_badge,
)
from shieldops.dashboard.config import STATUS_COLORS, SUPPORTED_ENVIRONMENTS

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------

st.set_page_config(
    page_title="ShieldOps",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_client() -> ShieldOpsAPIClient:
    token = st.session_state.get("auth_token")
    return ShieldOpsAPIClient(token=token)


# --- Login gate ---
if "auth_token" not in st.session_state:
    st.title("ShieldOps Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted and email and password:
            import httpx

            try:
                resp = httpx.post(
                    f"{ShieldOpsAPIClient().base_url}/auth/login",
                    json={"email": email, "password": password},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.session_state["auth_token"] = resp.json()["access_token"]
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except httpx.RequestError:
                st.error("Cannot connect to backend")
    st.stop()

client = get_client()

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------

st.sidebar.image(
    "https://img.shields.io/badge/ShieldOps-SRE%20Platform-blue?style=for-the-badge",
    use_container_width=True,
)
st.sidebar.markdown("### Filters")
env_filter = st.sidebar.selectbox(
    "Environment",
    ["All"] + SUPPORTED_ENVIRONMENTS,
    key="env_filter",
)
selected_env = None if env_filter == "All" else env_filter

render_auto_refresh(sidebar=True)

# ------------------------------------------------------------------
# Main content
# ------------------------------------------------------------------

render_page_header("Fleet Overview", "Real-time status of all ShieldOps agents and operations")

# --- KPI row ---
agents_data = client.list_agents(environment=selected_env)
inv_data = client.list_investigations(limit=1000)
rem_data = client.list_remediations(environment=selected_env, limit=1000)

total_agents = agents_data.get("total", 0)
total_investigations = inv_data.get("total", 0)
active_investigations = len(
    [
        i
        for i in inv_data.get("investigations", [])
        if i.get("status") in ("in_progress", "investigating")
    ]
)
resolved_count = len(
    [i for i in inv_data.get("investigations", []) if i.get("status") in ("complete", "success")]
)
pending_remediations = len(
    [
        r
        for r in rem_data.get("remediations", [])
        if r.get("status") in ("pending", "waiting_approval")
    ]
)

render_metric_row(
    [
        ("Agents Deployed", total_agents, None),
        ("Active Investigations", active_investigations, None),
        ("Resolved", resolved_count, None),
        ("Pending Remediations", pending_remediations, None),
    ]
)

st.divider()

# --- Agent health grid ---
st.subheader("Agent Health")

agents = agents_data.get("agents", [])
if agents:
    cols = st.columns(min(len(agents), 4))
    for idx, agent in enumerate(agents):
        with cols[idx % 4]:
            status = agent.get("status", "unknown")
            color = STATUS_COLORS.get(status, "#6B7280")
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:8px 12px;'
                f'margin-bottom:8px;border-radius:4px;background:#1E1E1E">'
                f"<strong>{agent.get('agent_id', 'unknown')}</strong><br/>"
                f"{render_status_badge(status)}"
                f"</div>",
                unsafe_allow_html=True,
            )
else:
    render_empty_state("No agents deployed. Start the backend to see agent status.")

st.divider()

# --- Live activity feed ---
st.subheader("Recent Activity")

tab_inv, tab_rem = st.tabs(["Investigations", "Remediations"])

with tab_inv:
    investigations = inv_data.get("investigations", [])[:10]
    if investigations:
        for inv in investigations:
            badge = render_status_badge(inv.get("status", "unknown"))
            name = inv.get("alert_name", inv.get("investigation_id", ""))
            conf = inv.get("confidence", 0)
            st.markdown(
                f"{badge} **{name}** — confidence {int(conf * 100)}%",
                unsafe_allow_html=True,
            )
    else:
        render_empty_state("No investigations yet.")

with tab_rem:
    remediations = rem_data.get("remediations", [])[:10]
    if remediations:
        render_data_table(
            remediations,
            columns=["remediation_id", "action_type", "target_resource", "status", "environment"],
        )
    else:
        render_empty_state("No remediations yet.")

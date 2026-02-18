"""Security page — posture score, CVEs, compliance, credential rotation."""

import plotly.graph_objects as go
import streamlit as st

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_auto_refresh,
    render_data_table,
    render_empty_state,
    render_metric_row,
    render_page_header,
)
from shieldops.dashboard.config import SUPPORTED_ENVIRONMENTS

st.set_page_config(page_title="Security | ShieldOps", page_icon="🔒", layout="wide")


@st.cache_resource
def get_client() -> ShieldOpsAPIClient:
    return ShieldOpsAPIClient()


client = get_client()

render_page_header("Security", "Security posture, CVE management, and compliance")
render_auto_refresh()

# --- Posture overview ---
posture = client.get_security_posture()

if "error" in posture:
    st.error(posture["error"])
else:
    score = posture.get("overall_score", 0)
    critical_cves = posture.get("critical_cves", 0)
    pending_patches = posture.get("pending_patches", 0)
    creds_expiring = posture.get("credentials_expiring_soon", 0)

    col_gauge, col_metrics = st.columns([1, 2])
    with col_gauge:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=score * 100 if score <= 1 else score,
                number={"suffix": ""},
                title={"text": "Posture Score"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#10B981"},
                    "steps": [
                        {"range": [0, 40], "color": "rgba(239,68,68,0.19)"},
                        {"range": [40, 70], "color": "rgba(245,158,11,0.19)"},
                        {"range": [70, 100], "color": "rgba(16,185,129,0.19)"},
                    ],
                },
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=250,
            margin={"l": 20, "r": 20, "t": 40, "b": 10},
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_metrics:
        render_metric_row(
            [
                ("Critical CVEs", critical_cves, None),
                ("Pending Patches", pending_patches, None),
                ("Credentials Expiring", creds_expiring, None),
            ]
        )

st.divider()

# --- Tabs ---
tab_cves, tab_compliance, tab_scans, tab_trigger = st.tabs(
    [
        "CVEs",
        "Compliance",
        "Scan History",
        "Trigger Scan",
    ]
)

# --- CVEs ---
with tab_cves:
    sev_filter = st.selectbox(
        "Severity",
        ["All", "critical", "high", "medium", "low"],
        key="cve_sev_filter",
    )
    sel_sev = None if sev_filter == "All" else sev_filter
    cve_data = client.list_cves(severity=sel_sev)

    if "error" in cve_data:
        st.error(cve_data["error"])
    else:
        cves = cve_data.get("cves", [])
        if cves:
            render_data_table(
                cves,
                columns=[
                    "cve_id",
                    "severity",
                    "package",
                    "affected_resource",
                    "cvss_score",
                    "patch_available",
                ],
            )
        else:
            render_empty_state("No CVEs found. Run a security scan to detect vulnerabilities.")

# --- Compliance ---
with tab_compliance:
    FRAMEWORKS = ["SOC2", "PCI-DSS", "HIPAA", "CIS"]
    cols = st.columns(len(FRAMEWORKS))
    for col, fw in zip(cols, FRAMEWORKS, strict=False):
        with col:
            comp = client.get_compliance(fw)
            score = comp.get("score", 0)
            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=score * 100 if score <= 1 else score,
                    number={"suffix": "%"},
                    title={"text": fw},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#3B82F6"},
                    },
                )
            )
            fig.update_layout(
                template="plotly_dark",
                height=200,
                margin={"l": 10, "r": 10, "t": 40, "b": 10},
            )
            st.plotly_chart(fig, use_container_width=True)
            controls = comp.get("controls", [])
            if controls:
                passing = sum(1 for c in controls if c.get("status") == "pass")
                st.caption(f"{passing}/{len(controls)} controls passing")

# --- Scan history ---
with tab_scans:
    scan_data = client.list_scans()
    if "error" in scan_data:
        st.error(scan_data["error"])
    else:
        scans = scan_data.get("scans", [])
        if scans:
            render_data_table(
                scans,
                columns=[
                    "scan_id",
                    "scan_type",
                    "status",
                    "environment",
                    "posture_score",
                    "critical_cves",
                ],
            )
        else:
            render_empty_state("No scans yet.")

# --- Trigger scan ---
with tab_trigger, st.form("trigger_scan"):
    st.markdown("#### Trigger Security Scan")
    environment = st.selectbox("Environment", SUPPORTED_ENVIRONMENTS, key="scan_env")
    scan_type = st.selectbox(
        "Scan Type",
        ["full", "cve_only", "credentials_only", "compliance_only"],
    )
    target_resources = st.text_input(
        "Target Resources (comma-separated)",
        placeholder="service-a, service-b",
    )
    frameworks = st.multiselect(
        "Compliance Frameworks",
        ["SOC2", "PCI-DSS", "HIPAA", "CIS"],
    )

    if st.form_submit_button("Start Scan"):
        targets = [t.strip() for t in target_resources.split(",") if t.strip()]
        result = client.trigger_scan(
            environment=environment,
            scan_type=scan_type,
            target_resources=targets or None,
            compliance_frameworks=frameworks or None,
        )
        if "error" in result:
            st.error(result["error"])
        else:
            st.success(f"Scan triggered: {result.get('message', 'OK')}")

"""Security Chat Agent — conversational AI for security operations.

A LangGraph tool-calling agent that can:
- Query vulnerability data
- Get remediation steps
- Trigger security scans
- Assign vulnerabilities to teams
- Analyze security posture

All destructive actions (scan triggers) are OPA policy gated.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()

SYSTEM_PROMPT = """\
You are ShieldOps Security Assistant, an AI-powered security operations expert.

You help security engineers by:
1. Analyzing vulnerability findings and prioritizing remediation
2. Providing specific remediation guidance for CVEs and misconfigurations
3. Explaining security posture and compliance status
4. Managing vulnerability lifecycle (triage, assignment, tracking)
5. Running targeted security scans when needed

When responding:
- Be specific and actionable
- Reference actual vulnerability data when available
- Suggest concrete next steps
- Warn about SLA breaches and critical findings
- Consider the blast radius of any recommended actions

Available tools: query_vulnerabilities, get_remediation_steps,
run_scan, assign_vulnerability, get_security_posture
"""

# Intent labels returned by _classify_intent
_INTENT_QUERY = "query_vulnerabilities"
_INTENT_REMEDIATION = "remediation_guidance"
_INTENT_SCAN = "run_scan"
_INTENT_ASSIGN = "assign_vulnerability"
_INTENT_POSTURE = "posture_overview"

# Keywords used for simple intent classification
_SCAN_KW = {"scan", "run scan", "trigger scan"}
_ASSIGN_KW = {"assign", "reassign", "delegate"}
_REMEDIATION_KW = {"remediate", "fix", "patch", "how to fix", "remediation"}
_POSTURE_KW = {"posture", "score", "overview", "summary", "status"}


class SecurityChatAgent:
    """Conversational security agent with tool-calling capabilities."""

    def __init__(
        self,
        repository: Any | None = None,
        security_runner: Any | None = None,
        policy_engine: Any | None = None,
    ) -> None:
        self._repository = repository
        self._security_runner = security_runner
        self._policy_engine = policy_engine

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def respond(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return a response with optional actions.

        Args:
            message: The user's message.
            history: Previous conversation messages (role/content dicts).
            context: Pre-fetched context data (e.g. vulnerability_stats).
            user_id: Current user ID for authorisation checks.

        Returns:
            Dict with ``response`` (str), ``actions`` (list), ``sources`` (list).
        """
        context = context or {}
        history = history or []

        intent = self._classify_intent(message)
        logger.info("chat_intent_classified", intent=intent, user=user_id)

        tool_results: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []

        if intent == _INTENT_QUERY:
            result = await self._tool_query_vulnerabilities(message, context)
            tool_results.append(result)

        elif intent == _INTENT_REMEDIATION:
            result = await self._tool_get_remediation(message, context)
            tool_results.append(result)

        elif intent == _INTENT_SCAN:
            result = await self._tool_run_scan(message, user_id)
            tool_results.append(result)
            if result.get("scan_id"):
                actions.append(
                    {
                        "type": "scan_started",
                        "label": f"View Scan {result['scan_id']}",
                        "data": {"scan_id": result["scan_id"]},
                    }
                )

        elif intent == _INTENT_ASSIGN:
            result = await self._tool_assign(message, context, user_id)
            tool_results.append(result)

        elif intent == _INTENT_POSTURE:
            result = await self._tool_get_posture(context)
            tool_results.append(result)

        response = await self._generate_response(message, history, context, tool_results, intent)

        return {
            "response": response,
            "actions": actions,
            "sources": [r.get("source", "") for r in tool_results if r.get("source")],
        }

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def _classify_intent(self, message: str) -> str:
        """Keyword-based intent classification.

        Checks from most-specific to least-specific to avoid false matches.
        Falls back to ``query_vulnerabilities`` when no keyword matches.
        """
        msg = message.lower()

        if any(kw in msg for kw in _SCAN_KW):
            return _INTENT_SCAN
        if any(kw in msg for kw in _ASSIGN_KW):
            return _INTENT_ASSIGN
        if any(kw in msg for kw in _REMEDIATION_KW):
            return _INTENT_REMEDIATION
        if any(kw in msg for kw in _POSTURE_KW):
            return _INTENT_POSTURE
        return _INTENT_QUERY

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _tool_query_vulnerabilities(
        self,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Query the vulnerability database and return stats + a filtered list."""
        if self._repository is None:
            return {"data": context.get("vulnerability_stats", {}), "source": "context"}

        try:
            stats = await self._repository.get_vulnerability_stats()

            msg = message.lower()
            severity: str | None = None
            if "critical" in msg:
                severity = "critical"
            elif "high" in msg:
                severity = "high"
            elif "medium" in msg:
                severity = "medium"
            elif "low" in msg:
                severity = "low"

            vulns = await self._repository.list_vulnerabilities(severity=severity, limit=10)
            return {
                "data": {
                    "stats": stats,
                    "vulnerabilities": vulns,
                    "severity_filter": severity,
                },
                "source": "vulnerability_db",
            }
        except Exception as exc:
            logger.error("chat_query_vulns_failed", error=str(exc))
            return {"data": {}, "error": str(exc)}

    async def _tool_get_remediation(
        self,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Return remediation guidance, optionally matched to a specific CVE."""
        cve_match = re.search(r"CVE-\d{4}-\d+", message, re.IGNORECASE)

        if cve_match and self._repository:
            cve_id = cve_match.group(0).upper()
            try:
                vulns = await self._repository.list_vulnerabilities(limit=200)
                matching = [v for v in vulns if v.get("cve_id") == cve_id]
                if matching:
                    vuln = matching[0]
                    return {
                        "data": {
                            "vulnerability": vuln,
                            "remediation_steps": vuln.get("remediation_steps", []),
                            "cve_id": cve_id,
                        },
                        "source": "vulnerability_db",
                    }
            except Exception as exc:
                logger.error("chat_remediation_lookup_failed", cve=cve_id, error=str(exc))
                return {"data": {}, "error": str(exc)}

        # No specific CVE — return generic guidance from context if available
        critical = context.get("critical_vulnerabilities", [])
        if critical:
            top = critical[0]
            return {
                "data": {
                    "message": "Showing guidance for the top critical finding.",
                    "vulnerability": top,
                    "remediation_steps": top.get("remediation_steps", []),
                },
                "source": "context",
            }

        return {
            "data": {"message": "No specific vulnerability found. Provide a CVE ID for details."},
            "source": "none",
        }

    async def _tool_run_scan(
        self,
        message: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        """Trigger a security scan via SecurityRunner, gated by OPA policy."""
        if self._security_runner is None:
            return {"error": "Security scanner not configured"}

        # OPA policy gate — fail closed on errors
        if self._policy_engine:
            try:
                from shieldops.models.base import Environment, RemediationAction, RiskLevel

                gate_action = RemediationAction(
                    id="chat-scan",
                    action_type="security_scan",
                    target_resource="*",
                    environment=Environment.PRODUCTION,
                    risk_level=RiskLevel.LOW,
                    parameters={},
                    description="Chat-triggered security scan",
                )
                decision = await self._policy_engine.evaluate(
                    action=gate_action,
                    agent_id=f"chat:{user_id or 'anonymous'}",
                )
                if not decision.allowed:
                    logger.warning(
                        "chat_scan_policy_denied",
                        user=user_id,
                        reasons=decision.reasons,
                    )
                    return {"error": (f"Scan denied by policy: {', '.join(decision.reasons)}")}
            except Exception as exc:
                logger.warning("chat_scan_policy_check_failed", error=str(exc))
                # Fail closed — do not proceed without a policy decision
                return {"error": f"Policy check failed: {exc}"}

        try:
            from shieldops.models.base import Environment

            msg = message.lower()
            scan_type = "full"
            if "container" in msg:
                scan_type = "container"
            elif "secret" in msg:
                scan_type = "git_secrets"
            elif "iac" in msg or "terraform" in msg:
                scan_type = "iac"
            elif "network" in msg:
                scan_type = "network"
            elif "k8s" in msg or "kubernetes" in msg:
                scan_type = "k8s_security"

            result = await self._security_runner.scan(
                scan_type=scan_type,
                environment=Environment.PRODUCTION,
            )
            logger.info(
                "chat_scan_triggered",
                scan_id=result.scan_id,
                scan_type=scan_type,
                user=user_id,
            )
            return {
                "scan_id": result.scan_id,
                "scan_type": scan_type,
                "cve_count": len(result.cve_findings),
                "source": "security_runner",
            }
        except Exception as exc:
            logger.error("chat_scan_failed", error=str(exc))
            return {"error": str(exc)}

    async def _tool_assign(
        self,
        message: str,
        context: dict[str, Any],
        user_id: str | None,
    ) -> dict[str, Any]:
        """Extract vuln + team and call repository.assign_vulnerability."""
        if self._repository is None:
            return {"error": "Repository not configured"}

        vuln_match = re.search(r"(vuln-[a-z0-9]+|CVE-\d{4}-\d+)", message, re.IGNORECASE)
        team_match = re.search(r"team[:\s]+(\w+)", message, re.IGNORECASE)

        if not vuln_match:
            return {
                "error": (
                    "Could not identify a vulnerability ID in your message. "
                    "Please include a vuln-ID or CVE-ID."
                )
            }

        vuln_id = vuln_match.group(0)
        team_name = team_match.group(1) if team_match else None

        team_id: str | None = None
        if team_name:
            try:
                teams = await self._repository.list_teams()
                for team in teams:
                    if team_name.lower() in team.get("name", "").lower():
                        team_id = team["id"]
                        break
            except Exception as exc:
                logger.error("chat_team_lookup_failed", error=str(exc))
                return {"error": f"Team lookup failed: {exc}"}

        try:
            success = await self._repository.assign_vulnerability(vuln_id, team_id=team_id)
            logger.info(
                "chat_vuln_assigned",
                vuln_id=vuln_id,
                team_id=team_id,
                user=user_id,
                success=success,
            )
            return {
                "assigned": success,
                "vulnerability_id": vuln_id,
                "team_id": team_id,
                "source": "vulnerability_db",
            }
        except Exception as exc:
            logger.error("chat_assign_failed", error=str(exc))
            return {"error": str(exc)}

    async def _tool_get_posture(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Aggregate security posture data from the repository or context cache."""
        data: dict[str, Any] = {}

        # Prefer live data from repository; fall back to pre-fetched context
        if self._repository:
            try:
                data["stats"] = await self._repository.get_vulnerability_stats()
                sla_breaches = await self._repository.list_vulnerabilities(
                    sla_breached=True, limit=5
                )
                data["sla_breaches"] = sla_breaches
            except Exception as exc:
                logger.error("chat_posture_db_failed", error=str(exc))
                # Fall back to context
                if context.get("vulnerability_stats"):
                    data["stats"] = context["vulnerability_stats"]
        else:
            if context.get("vulnerability_stats"):
                data["stats"] = context["vulnerability_stats"]
            if context.get("sla_breaches"):
                data["sla_breaches"] = context["sla_breaches"]

        return {"data": data, "source": "posture_analysis"}

    # ------------------------------------------------------------------
    # LLM response generation
    # ------------------------------------------------------------------

    async def _generate_response(
        self,
        message: str,
        history: list[dict[str, Any]],
        context: dict[str, Any],
        tool_results: list[dict[str, Any]],
        intent: str,
    ) -> str:
        """Generate a natural-language response using llm_structured.

        Falls back to a rule-based response when the LLM call fails so that
        the user always receives a meaningful reply.
        """
        try:
            from pydantic import BaseModel as _BaseModel

            from shieldops.utils.llm import llm_structured

            class _ResponseSchema(_BaseModel):
                response: str

            tool_context = "\n".join(
                f"Tool result ({intent}): {str(r)[:600]}" for r in tool_results
            )

            history_context = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in history[-4:])

            user_prompt = (
                f"Conversation history:\n{history_context}\n\n"
                f"Tool data:\n{tool_context}\n\n"
                f"User message: {message}\n\n"
                "Respond helpfully based on the data above. Be concise and actionable."
            )

            result = await llm_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=_ResponseSchema,
            )
            return result.response  # type: ignore[union-attr]

        except Exception as exc:
            logger.error("chat_llm_response_failed", error=str(exc))
            return self._fallback_text(tool_results)

    def _fallback_text(self, tool_results: list[dict[str, Any]]) -> str:
        """Build a plain-text fallback response from tool result data."""
        for tr in tool_results:
            if tr.get("error"):
                return f"I encountered an issue: {tr['error']}"

            data = tr.get("data", {})
            if not data:
                continue

            # Posture / stats block
            stats = data.get("stats") if isinstance(data, dict) else None
            if stats and isinstance(stats, dict):
                by_sev = stats.get("by_severity", {})
                return (
                    f"Current security overview:\n"
                    f"  Total vulnerabilities : {stats.get('total', 'N/A')}\n"
                    f"  By severity           : {by_sev}\n"
                    f"  SLA breaches          : {stats.get('sla_breaches', 0)}"
                )

            # Scan result block
            if isinstance(data, dict) and tr.get("source") == "security_runner":
                return (
                    f"Scan started: {tr.get('scan_id', 'unknown')} "
                    f"({tr.get('scan_type', 'full')}). "
                    f"CVEs found so far: {tr.get('cve_count', 0)}."
                )

            # Assignment block
            if isinstance(data, dict) and "assigned" in data:
                return (
                    f"Vulnerability {data.get('vulnerability_id')} "
                    f"{'assigned' if data.get('assigned') else 'assignment failed'}."
                )

        return "I'm ready to help with security questions. What would you like to know?"

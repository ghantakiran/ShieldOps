"""TLS certificate monitoring — remote domains and Kubernetes TLS secrets."""

from __future__ import annotations

import asyncio
import base64
import json
import ssl
from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.security_agent.models import CertificateStatus

logger = structlog.get_logger(__name__)


class CertificateMonitor:
    """Monitors TLS certificate expiry for domains and K8s secrets."""

    def __init__(self) -> None:
        self._certificates: list[CertificateStatus] = []

    # ------------------------------------------------------------------
    # Remote domain checks
    # ------------------------------------------------------------------

    async def check_certificate(self, domain: str, port: int = 443) -> CertificateStatus:
        """Connect to *domain*:*port* via TLS, extract certificate info.

        Uses :func:`asyncio.open_connection` with an SSL context so the
        entire operation is non-blocking.
        """
        logger.info("cert_monitor.check", domain=domain, port=port)
        try:
            ctx = ssl.create_default_context()
            reader, writer = await asyncio.open_connection(
                domain, port, ssl=ctx, server_hostname=domain
            )
            ssl_obj = writer.transport.get_extra_info("ssl_object")
            cert: dict[str, Any] = ssl_obj.getpeercert()  # type: ignore[assignment,union-attr]
            writer.close()
            await writer.wait_closed()

            return self._parse_peer_cert(cert, domain)
        except Exception:
            logger.exception("cert_monitor.check_failed", domain=domain, port=port)
            return CertificateStatus(domain=domain, is_expired=True, days_until_expiry=-1)

    # ------------------------------------------------------------------
    # Kubernetes TLS secrets
    # ------------------------------------------------------------------

    async def scan_kubernetes_secrets(self, namespace: str) -> list[CertificateStatus]:
        """Find ``kubernetes.io/tls`` secrets in *namespace*, parse certs."""
        logger.info("cert_monitor.k8s_secrets_start", namespace=namespace)
        raw = await self._kubectl_json(
            "get",
            "secrets",
            "-n",
            namespace,
            "--field-selector",
            "type=kubernetes.io/tls",
            "-o",
            "json",
        )
        if raw is None:
            return []

        results: list[CertificateStatus] = []
        for secret in raw.get("items", []):
            name = secret.get("metadata", {}).get("name", "unknown")
            tls_crt_b64 = secret.get("data", {}).get("tls.crt", "")
            if not tls_crt_b64:
                continue

            cert_status = await self._parse_pem_from_b64(
                tls_crt_b64, domain_hint=f"k8s-secret/{namespace}/{name}"
            )
            if cert_status:
                results.append(cert_status)

        self._certificates.extend(results)
        logger.info(
            "cert_monitor.k8s_secrets_complete",
            namespace=namespace,
            certs_found=len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Expiry filtering and alerting
    # ------------------------------------------------------------------

    async def get_expiring_certificates(self, days_threshold: int = 30) -> list[CertificateStatus]:
        """Return certificates expiring within *days_threshold* days."""
        return [c for c in self._certificates if c.days_until_expiry <= days_threshold]

    async def generate_renewal_alert(self, cert: CertificateStatus) -> dict[str, str | int | bool]:
        """Create an alert payload for an expiring or expired certificate."""
        if cert.is_expired:
            urgency = "critical"
            title = f"EXPIRED certificate: {cert.domain}"
        elif cert.days_until_expiry <= 7:
            urgency = "critical"
            title = f"Certificate for {cert.domain} expires in {cert.days_until_expiry} day(s)"
        elif cert.days_until_expiry <= 30:
            urgency = "high"
            title = f"Certificate for {cert.domain} expires in {cert.days_until_expiry} day(s)"
        else:
            urgency = "info"
            title = f"Certificate for {cert.domain} expires in {cert.days_until_expiry} day(s)"

        return {
            "title": title,
            "domain": cert.domain,
            "issuer": cert.issuer,
            "days_until_expiry": cert.days_until_expiry,
            "is_expired": cert.is_expired,
            "urgency": urgency,
            "serial_number": cert.serial_number,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_peer_cert(cert: dict[str, Any], domain: str) -> CertificateStatus:
        """Parse the dict returned by ``ssl.SSLSocket.getpeercert()``."""
        not_before_str = cert.get("notBefore", "")
        not_after_str = cert.get("notAfter", "")
        # Python's ssl module uses e.g. "Sep 11 00:00:00 2024 GMT"
        fmt = "%b %d %H:%M:%S %Y %Z"

        not_before: datetime | None = None
        not_after: datetime | None = None
        try:
            if not_before_str:
                not_before = datetime.strptime(not_before_str, fmt)
            if not_after_str:
                not_after = datetime.strptime(not_after_str, fmt)
        except ValueError:
            pass

        now = datetime.now(tz=UTC).replace(tzinfo=None)
        days_until = (not_after - now).days if not_after else -1
        is_expired = days_until < 0

        issuer_parts: tuple[Any, ...] = cert.get("issuer", ())
        issuer_str = ""
        for rdn in issuer_parts:
            for attr_tuple in rdn:
                if attr_tuple[0] == "organizationName":
                    issuer_str = attr_tuple[1]

        serial = cert.get("serialNumber", "")

        return CertificateStatus(
            domain=domain,
            issuer=issuer_str,
            not_before=not_before,
            not_after=not_after,
            days_until_expiry=days_until,
            is_expired=is_expired,
            serial_number=serial,
        )

    async def _parse_pem_from_b64(
        self, b64_data: str, *, domain_hint: str
    ) -> CertificateStatus | None:
        """Decode a base64-encoded PEM cert and extract expiry info.

        Uses ``openssl x509`` via subprocess so we don't need a crypto
        library dependency.
        """
        try:
            pem_bytes = base64.b64decode(b64_data)
        except Exception:
            logger.error("cert_monitor.b64_decode_error", domain=domain_hint)
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                "openssl",
                "x509",
                "-noout",
                "-dates",
                "-issuer",
                "-serial",
                "-fingerprint",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate(input=pem_bytes)
            output = stdout.decode()
        except FileNotFoundError:
            logger.error("cert_monitor.openssl_not_found")
            return None
        except Exception:
            logger.exception("cert_monitor.openssl_error")
            return None

        return self._parse_openssl_output(output, domain_hint)

    @staticmethod
    def _parse_openssl_output(output: str, domain: str) -> CertificateStatus:
        """Parse ``openssl x509`` text output into a CertificateStatus."""
        lines = output.strip().splitlines()
        info: dict[str, str] = {}
        for line in lines:
            if "=" in line:
                key, _, val = line.partition("=")
                info[key.strip()] = val.strip()

        fmt = "%b %d %H:%M:%S %Y %Z"
        not_before: datetime | None = None
        not_after: datetime | None = None
        try:
            nb = info.get("notBefore", "")
            if nb:
                not_before = datetime.strptime(nb, fmt)
            na = info.get("notAfter", "")
            if na:
                not_after = datetime.strptime(na, fmt)
        except ValueError:
            pass

        now = datetime.now(tz=UTC).replace(tzinfo=None)
        days_until = (not_after - now).days if not_after else -1
        is_expired = days_until < 0

        return CertificateStatus(
            domain=domain,
            issuer=info.get("issuer", ""),
            not_before=not_before,
            not_after=not_after,
            days_until_expiry=days_until,
            is_expired=is_expired,
            serial_number=info.get("serial", ""),
            fingerprint=info.get("SHA256 Fingerprint", ""),
        )

    @staticmethod
    async def _kubectl_json(*args: str) -> dict[str, Any] | None:
        """Run a kubectl command and return parsed JSON, or None."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "kubectl",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(
                    "cert_monitor.kubectl_error",
                    stderr=stderr.decode(errors="replace")[:500],
                )
                return None
            result: dict[str, Any] = json.loads(stdout.decode())
            return result
        except FileNotFoundError:
            logger.error("cert_monitor.kubectl_not_found")
            return None
        except Exception:
            logger.exception("cert_monitor.kubectl_unexpected")
            return None

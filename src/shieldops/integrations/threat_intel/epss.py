"""EPSS (Exploit Prediction Scoring System) integration.

Queries the FIRST.org EPSS API to score CVEs by their probability
of being exploited in the wild within the next 30 days.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


class EPSSScorer:
    """Scores CVEs using the FIRST.org EPSS API.

    Caches scores for a configurable TTL to reduce API calls.

    Args:
        base_url: EPSS API endpoint.
        cache_ttl_seconds: How long to cache scores.
    """

    def __init__(
        self,
        base_url: str = "https://api.first.org/data/v1/epss",
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self._base_url = base_url
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_time: datetime | None = None
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                headers={"Accept": "application/json"},
                timeout=30,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _is_cache_valid(self) -> bool:
        if self._cache_time is None:
            return False
        return datetime.now(UTC) - self._cache_time < timedelta(seconds=self._cache_ttl)

    async def score(self, cve_id: str) -> dict[str, Any]:
        """Get the EPSS score for a single CVE.

        Returns:
            Dict with cve_id, epss_score (0-1), percentile, and risk_level.
        """
        if self._is_cache_valid() and cve_id in self._cache:
            return self._cache[cve_id]

        try:
            result = await self._fetch_scores([cve_id])
            if cve_id in result:
                return result[cve_id]
        except Exception as e:
            logger.error("epss_score_failed", cve_id=cve_id, error=str(e))

        return {
            "cve_id": cve_id,
            "epss_score": 0.0,
            "percentile": 0.0,
            "risk_level": "unknown",
            "error": "Failed to fetch EPSS score",
        }

    async def score_bulk(self, cve_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get EPSS scores for multiple CVEs in a single request.

        Args:
            cve_ids: List of CVE IDs (e.g. ["CVE-2023-1234", "CVE-2023-5678"]).

        Returns:
            Dict mapping cve_id to score details.
        """
        # Check cache for all requested CVEs
        results: dict[str, dict[str, Any]] = {}
        uncached: list[str] = []

        if self._is_cache_valid():
            for cve_id in cve_ids:
                if cve_id in self._cache:
                    results[cve_id] = self._cache[cve_id]
                else:
                    uncached.append(cve_id)
        else:
            uncached = list(cve_ids)

        if uncached:
            try:
                fetched = await self._fetch_scores(uncached)
                results.update(fetched)
            except Exception as e:
                logger.error("epss_bulk_score_failed", count=len(uncached), error=str(e))
                for cve_id in uncached:
                    results[cve_id] = {
                        "cve_id": cve_id,
                        "epss_score": 0.0,
                        "percentile": 0.0,
                        "risk_level": "unknown",
                    }

        return results

    async def _fetch_scores(self, cve_ids: list[str]) -> dict[str, dict[str, Any]]:
        client = self._ensure_client()

        # EPSS API accepts comma-separated CVE IDs
        cve_param = ",".join(cve_ids)
        response = await client.get(
            self._base_url,
            params={"cve": cve_param},
        )
        response.raise_for_status()
        data = response.json()

        results: dict[str, dict[str, Any]] = {}
        for entry in data.get("data", []):
            cve_id = entry.get("cve", "")
            epss_score = float(entry.get("epss", 0.0))
            percentile = float(entry.get("percentile", 0.0))

            result = {
                "cve_id": cve_id,
                "epss_score": epss_score,
                "percentile": percentile,
                "risk_level": self._classify_risk(epss_score),
            }
            results[cve_id] = result
            self._cache[cve_id] = result

        self._cache_time = datetime.now(UTC)

        logger.info(
            "epss_scores_fetched",
            requested=len(cve_ids),
            returned=len(results),
        )
        return results

    @staticmethod
    def _classify_risk(epss_score: float) -> str:
        """Classify EPSS score into risk levels."""
        if epss_score >= 0.7:
            return "critical"
        elif epss_score >= 0.4:
            return "high"
        elif epss_score >= 0.1:
            return "medium"
        elif epss_score > 0:
            return "low"
        return "unknown"

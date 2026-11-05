import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

import httpx

from src.urja_api.client.auth import SessionManager
from src.urja_api.config import settings
from src.urja_api.errors import (
    NotFoundError,
    UpstreamPortalError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

logger = logging.getLogger("urja_api.client")


class UrjaPortalClient:
    """
    Polite, resilient async HTTP client for Urja Meter Ops.
    Features:
    - Max 2 concurrent in-flight requests (asyncio.Semaphore)
    - Rate delay between requests
    - Single-flight re-login on session expiration (HTTP 302 -> /login)
    - Bounded exponential backoff retries with jitter
    - Error mapping to domain exceptions
    """

    def __init__(self, session_manager: Optional[SessionManager] = None):
        self.session_manager = session_manager or SessionManager()
        self.semaphore = asyncio.Semaphore(settings.max_concurrency)
        self.client = httpx.AsyncClient(
            base_url=settings.portal_base_url,
            headers={"User-Agent": settings.portal_user_agent},
            timeout=settings.timeout_sec,
            follow_redirects=False,
        )

    async def close(self):
        await self.client.aclose()

    async def _polite_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_required: bool = True,
        max_retries: int = 3,
    ) -> httpx.Response:
        async with self.semaphore:
            # Polite client inter-request delay
            if settings.request_delay_sec > 0:
                await asyncio.sleep(settings.request_delay_sec)

            req_headers = dict(headers or {})

            if auth_required:
                token = await self.session_manager.get_valid_session_cookie(self.client)
                req_headers["Cookie"] = f"__Secure-better-auth.session_token={token}"

            attempt = 0
            while attempt <= max_retries:
                attempt += 1
                try:
                    res = await self.client.request(method=method, url=path, params=params, headers=req_headers)

                    # Check for session expiration (HTTP 302 to /login or redirect)
                    if auth_required and res.status_code in (302, 303):
                        loc = res.headers.get("location", "")
                        if "login" in loc or loc == "/login":
                            logger.warning("Portal returned 302 redirect to /login. Invalidation triggered.")
                            await self.session_manager.invalidate_session()
                            if attempt <= max_retries:
                                # Re-login and refresh cookie
                                token = await self.session_manager.get_valid_session_cookie(self.client)
                                req_headers["Cookie"] = f"__Secure-better-auth.session_token={token}"
                                continue

                    # Check for transient upstream failures (429 or 5xx)
                    if res.status_code in (429, 500, 502, 503, 504) and attempt <= max_retries:
                        backoff = (2 ** (attempt - 1)) * 0.5 + random.uniform(0.1, 0.3)
                        logger.warning(
                            "Upstream status %s on %s. Retrying in %.2fs (attempt %d/%d)",
                            res.status_code,
                            path,
                            backoff,
                            attempt,
                            max_retries,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    # Handle 404
                    if res.status_code == 404:
                        raise NotFoundError("Portal entity", path)

                    if res.status_code >= 400:
                        raise UpstreamPortalError(f"Upstream portal returned HTTP {res.status_code} on {path}.")

                    return res

                except httpx.TimeoutException as e:
                    if attempt <= max_retries:
                        backoff = (2 ** (attempt - 1)) * 0.5
                        logger.warning("Timeout connecting to portal %s. Retrying in %.2fs", path, backoff)
                        await asyncio.sleep(backoff)
                        continue
                    raise UpstreamTimeoutError(f"Portal timed out on {path}: {e}")

                except httpx.RequestError as e:
                    if attempt <= max_retries:
                        backoff = (2 ** (attempt - 1)) * 0.5
                        await asyncio.sleep(backoff)
                        continue
                    raise UpstreamUnavailableError(f"Portal unreachable on {path}: {type(e).__name__}")

            raise UpstreamPortalError(f"Exceeded max retries for {path}.")

    async def fetch_meters_bulk(self) -> Dict[str, Any]:
        """Fetches full meter export via HMAC-signed export route."""
        ts, sig = await self.session_manager.get_export_signature(self.client, path="/portal/export", query="page=1")
        headers = {"x-timestamp": ts, "x-signature": sig}
        res = await self._polite_request("GET", "/portal/export", params={"page": 1}, headers=headers)
        return res.json()

    async def search_meters_paged(self, query: str = "", page: int = 1) -> Dict[str, Any]:
        """Queries portal meter search endpoint."""
        res = await self._polite_request("GET", "/portal/meters/search", params={"q": query, "page": page})
        return res.json()

    async def fetch_dts_paged(self, page: int = 1) -> Dict[str, Any]:
        """Queries distribution transformers page."""
        res = await self._polite_request("GET", "/portal/dts", params={"page": page})
        return res.json()

    async def fetch_all_dts(self) -> List[Dict[str, Any]]:
        """Fetches all DTs by traversing pages until exhausted."""
        all_dts = []
        page = 1
        while True:
            data = await self.fetch_dts_paged(page)
            dt_list = data.get("data", [])
            if not dt_list:
                break
            all_dts.extend(dt_list)
            total = data.get("total", 0)
            if len(all_dts) >= total:
                break
            page += 1
        return all_dts

    async def fetch_meter_geo(self, meter_id: str) -> Dict[str, Any]:
        """Fetches coordinates for a single meter."""
        res = await self._polite_request("GET", f"/portal/meters/{meter_id}/geo")
        return res.json()

    async def fetch_meter_energy(
        self, meter_id: str, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches telemetry readings for a meter with optional YYYY-MM-DD boundaries."""
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        res = await self._polite_request("GET", f"/portal/meters/{meter_id}/energy", params=params)
        return res.json()

    async def fetch_meter_detail_html(self, meter_id: str) -> str:
        """Fetches raw meter detail HTML page."""
        res = await self._polite_request("GET", f"/meters/{meter_id}")
        return res.text

    async def check_health(self) -> Dict[str, Any]:
        """Probes portal to measure latency and reachability."""
        t0 = time.perf_counter()
        try:
            res = await self.client.get("/login", timeout=5.0)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            is_ok = res.status_code in (200, 302)
            return {
                "is_reachable": is_ok,
                "http_status": res.status_code,
                "latency_ms": latency_ms,
                "error_message": None if is_ok else f"HTTP {res.status_code}",
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {"is_reachable": False, "http_status": None, "latency_ms": latency_ms, "error_message": str(e)}

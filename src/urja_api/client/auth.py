import asyncio
import hashlib
import hmac
import logging
import time
from typing import Optional, Tuple

import httpx

from src.urja_api.config import settings
from src.urja_api.errors import UpstreamPortalError, UpstreamUnavailableError

logger = logging.getLogger("urja_api.auth")


class SessionManager:
    """
    Manages session lifecycle with Urja Meter Ops portal.
    Features:
    - Single-flight re-login using asyncio.Lock
    - Proactive session refresh before 60-minute expiry
    - HMAC-SHA256 signing key caching and computation for bulk export
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._session_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._signing_secret: Optional[str] = None
        self._secret_fetched_at: float = 0.0

    @property
    def is_authenticated(self) -> bool:
        # Require 120 seconds buffer before token expiry
        return bool(self._session_token and time.time() < (self._token_expires_at - 120))

    async def get_valid_session_cookie(self, client: httpx.AsyncClient) -> str:
        """Returns a valid session token, logging in if expired or absent (single-flight)."""
        if self.is_authenticated and self._session_token:
            return self._session_token

        async with self._lock:
            # Double check after acquiring lock
            if self.is_authenticated and self._session_token:
                return self._session_token

            logger.info("Session expired or uninitialized. Initiating single-flight login.")
            await self._login(client)
            if not self._session_token:
                raise UpstreamPortalError("Failed to obtain valid session token from portal.")
            return self._session_token

    async def invalidate_session(self):
        """Forces next request to re-authenticate."""
        async with self._lock:
            self._session_token = None
            self._token_expires_at = 0.0

    async def invalidate_signing_secret(self):
        """Forces next export signature generation to fetch fresh signing keys."""
        async with self._lock:
            self._signing_secret = None
            self._secret_fetched_at = 0.0

    async def _login(self, client: httpx.AsyncClient):
        if not settings.portal_username or not settings.portal_password:
            raise UpstreamPortalError("Portal credentials not configured in environment.")

        login_url = f"{settings.portal_base_url}/login"
        headers = {
            "Origin": settings.portal_base_url,
            "Referer": login_url,
            "Accept": "application/json",
            "User-Agent": settings.portal_user_agent,
        }
        data = {"email": settings.portal_username, "password": settings.portal_password}

        try:
            res = await client.post(login_url, data=data, headers=headers, follow_redirects=False)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.error("Network error during portal login: %s", type(e).__name__)
            raise UpstreamUnavailableError(f"Unable to reach portal for authentication: {type(e).__name__}")

        if res.status_code == 403:
            raise UpstreamPortalError("Portal rejected login with 403 (Origin/CSRF validation failure).")

        # Check cookies
        token = res.cookies.get("__Secure-better-auth.session_token")
        if not token:
            # Check Set-Cookie headers directly in case cookies weren't stored
            set_cookie = res.headers.get("set-cookie", "")
            if "__Secure-better-auth.session_token=" in set_cookie:
                import re

                m = re.search(r"__Secure-better-auth\.session_token=([^;]+)", set_cookie)
                if m:
                    token = m.group(1)

        if not token:
            logger.error("Portal login failed: status=%s, response=%s", res.status_code, res.text[:200])
            raise UpstreamPortalError("Invalid portal credentials or missing session token.")

        self._session_token = token
        # Token valid for 3600 seconds
        self._token_expires_at = time.time() + 3600
        logger.info("Successfully established portal session token.")

    async def get_export_signature(
        self, client: httpx.AsyncClient, path: str = "/portal/export", query: str = "page=1"
    ) -> Tuple[str, str]:
        """Obtains signing secret and computes HMAC SHA-256 for export endpoint."""
        token = await self.get_valid_session_cookie(client)

        async with self._lock:
            # Refresh secret every 30 minutes
            if not self._signing_secret or (time.time() - self._secret_fetched_at > 1800):
                keys_url = f"{settings.portal_base_url}/portal/keys"
                res = await client.get(keys_url, headers={"Cookie": f"__Secure-better-auth.session_token={token}"})
                if res.status_code != 200:
                    raise UpstreamPortalError(f"Failed to fetch signing keys (status {res.status_code}).")
                secret = res.json().get("data", {}).get("signingSecret")
                if not secret:
                    raise UpstreamPortalError("Portal keys payload did not contain signingSecret.")
                self._signing_secret = secret
                self._secret_fetched_at = time.time()

            timestamp = str(int(time.time()))
            payload = f"GET\n{path}\n{query}\n{timestamp}".encode("utf-8")
            signature = hmac.new(self._signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
            return timestamp, signature

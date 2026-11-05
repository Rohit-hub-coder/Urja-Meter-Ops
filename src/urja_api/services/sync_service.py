import asyncio
import logging
import time
from typing import Any, Dict, Optional

from src.urja_api.client.portal_client import UrjaPortalClient
from src.urja_api.config import settings
from src.urja_api.errors import RateLimitExceededError, UpstreamPortalError
from src.urja_api.parsers.meter_parser import parse_meter_from_export
from src.urja_api.storage.repository import MeterRepository

logger = logging.getLogger("urja_api.sync")


class SyncService:
    def __init__(self, portal_client: Optional[UrjaPortalClient] = None, repository: Optional[MeterRepository] = None):
        self.portal_client = portal_client or UrjaPortalClient()
        self.repository = repository or MeterRepository()
        self._lock = asyncio.Lock()
        self._last_sync_time: float = 0.0

    async def sync_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Executes idempotent bulk synchronization of the complete portal dataset into SQLite.
        Enforces a cooldown rate limit on manual triggers to protect the legacy portal.
        """
        async with self._lock:
            now = time.time()
            if not force and (now - self._last_sync_time < settings.sync_cooldown_sec):
                wait_sec = int(settings.sync_cooldown_sec - (now - self._last_sync_time))
                raise RateLimitExceededError(
                    f"Sync cooldown active. Please wait {wait_sec} seconds before synchronizing again."
                )

            logger.info("Starting bulk dataset synchronization from Urja portal...")
            t0 = time.perf_counter()

            try:
                # 1. Fetch DTs
                dts = await self.portal_client.fetch_all_dts()
                await self.repository.upsert_transformers(dts)

                # 2. Fetch full meters export
                export_json = await self.portal_client.fetch_meters_bulk()
                raw_meters = export_json.get("data", [])
                if not raw_meters:
                    raise UpstreamPortalError("Bulk export endpoint returned 0 meter records.")

                # 3. Parse and normalize
                parsed_meters = [parse_meter_from_export(m) for m in raw_meters]

                # 4. Upsert into SQLite
                await self.repository.upsert_meters(parsed_meters)
                await self.repository.record_sync_metadata("meters_bulk", len(parsed_meters), "success")

                self._last_sync_time = time.time()
                duration_ms = round((time.perf_counter() - t0) * 1000, 2)

                logger.info(
                    "Bulk synchronization complete: %d meters, %d DTs in %sms",
                    len(parsed_meters),
                    len(dts),
                    duration_ms,
                )

                return {
                    "status": "success",
                    "total_meters_synced": len(parsed_meters),
                    "total_dts_synced": len(dts),
                    "duration_ms": duration_ms,
                    "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._last_sync_time)),
                }

            except Exception as e:
                logger.error("Bulk synchronization failed: %s", e)
                await self.repository.record_sync_metadata("meters_bulk", 0, f"error: {str(e)}")
                raise

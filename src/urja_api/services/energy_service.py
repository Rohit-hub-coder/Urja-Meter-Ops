import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from src.urja_api.client.portal_client import UrjaPortalClient
from src.urja_api.config import settings
from src.urja_api.models.consumption import MeterConsumptionResponse
from src.urja_api.parsers.energy_parser import parse_energy_telemetry


class EnergyService:
    def __init__(self, portal_client: Optional[UrjaPortalClient] = None):
        self.portal_client = portal_client or UrjaPortalClient()
        # In-memory LRU/TTL cache for telemetry: (meter_id, from_date, to_date) -> (timestamp, MeterConsumptionResponse)
        self._cache: Dict[Tuple[str, Optional[str], Optional[str]], Tuple[float, MeterConsumptionResponse]] = {}

    async def get_meter_consumption(
        self, meter_id: str, from_dt: Optional[datetime] = None, to_dt: Optional[datetime] = None
    ) -> MeterConsumptionResponse:
        from_date_str = from_dt.strftime("%Y-%m-%d") if from_dt else None
        to_date_str = to_dt.strftime("%Y-%m-%d") if to_dt else None
        cache_key = (meter_id, from_date_str, to_date_str)

        # Check in-memory cache TTL (15 min = 900s)
        now = time.time()
        if cache_key in self._cache:
            cached_at, cached_resp = self._cache[cache_key]
            if (now - cached_at) < settings.cache_ttl_consumption_sec:
                return cached_resp

        # Fetch from upstream portal
        raw_resp = await self.portal_client.fetch_meter_energy(
            meter_id=meter_id, from_date=from_date_str, to_date=to_date_str
        )
        readings = raw_resp.get("data", [])

        # Parse, compute deltas and window summary
        parsed = parse_energy_telemetry(meter_id=meter_id, raw_readings=readings, from_dt=from_dt, to_dt=to_dt)

        self._cache[cache_key] = (now, parsed)
        return parsed

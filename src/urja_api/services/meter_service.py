from typing import List, Optional, Tuple

from src.urja_api.client.portal_client import UrjaPortalClient
from src.urja_api.errors import NotFoundError
from src.urja_api.models.common import PaginationMetadata
from src.urja_api.models.meter import MeterDetail, MeterSummary
from src.urja_api.parsers.meter_parser import parse_meter_detail_from_html
from src.urja_api.services.sync_service import SyncService
from src.urja_api.storage.repository import MeterRepository


class MeterService:
    def __init__(
        self,
        repository: Optional[MeterRepository] = None,
        portal_client: Optional[UrjaPortalClient] = None,
        sync_service: Optional[SyncService] = None,
    ):
        self.repository = repository or MeterRepository()
        self.portal_client = portal_client or UrjaPortalClient()
        self.sync_service = sync_service or SyncService(self.portal_client, self.repository)

    async def list_meters(
        self,
        query: Optional[str] = None,
        make: Optional[str] = None,
        install_status: Optional[str] = None,
        phase_type: Optional[str] = None,
        dt_code: Optional[str] = None,
        feeder_code: Optional[str] = None,
        near_lat: Optional[float] = None,
        near_lng: Optional[float] = None,
        radius_km: Optional[float] = None,
        sort_by: str = "meter_id",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[MeterSummary], PaginationMetadata]:
        # Check if database is populated; if empty, perform initial sync
        total_count = await self.repository.get_total_meters_count()
        if total_count == 0:
            await self.sync_service.sync_all(force=True)

        return await self.repository.query_meters(
            query=query,
            make=make,
            install_status=install_status,
            phase_type=phase_type,
            dt_code=dt_code,
            feeder_code=feeder_code,
            near_lat=near_lat,
            near_lng=near_lng,
            radius_km=radius_km,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            limit=limit,
        )

    async def get_meter(self, meter_id: str) -> MeterDetail:
        meter = await self.repository.get_meter_by_id(meter_id)
        if meter:
            return meter

        # If not in local index, try live portal fallback
        try:
            html = await self.portal_client.fetch_meter_detail_html(meter_id)
            return parse_meter_detail_from_html(html, meter_id)
        except Exception:
            raise NotFoundError("Meter", meter_id)

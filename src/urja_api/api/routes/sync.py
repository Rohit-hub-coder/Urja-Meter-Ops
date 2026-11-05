from fastapi import APIRouter, Depends, Query

from src.urja_api.api.dependencies import get_repository, get_sync_service
from src.urja_api.services.sync_service import SyncService
from src.urja_api.storage.repository import MeterRepository

router = APIRouter(prefix="/api/v1/sync", tags=["Synchronization"])


@router.post(
    "",
    summary="Trigger bulk synchronization from portal",
    description="Synchronizes the complete dataset (all meters and distribution transformers) from the Urja portal into the local SQLite index. Rate limited by cooldown.",
)
async def trigger_sync(
    force: bool = Query(False, description="Bypass the cooldown period (use with caution)."),
    sync_service: SyncService = Depends(get_sync_service),
):
    return await sync_service.sync_all(force=force)


@router.get(
    "/status",
    summary="Check dataset synchronization status",
    description="Returns the status of the local SQLite index, record count, and timestamp of the last successful synchronization.",
)
async def get_sync_status(repo: MeterRepository = Depends(get_repository)):
    metadata = await repo.get_sync_metadata("meters_bulk")
    total_meters = await repo.get_total_meters_count()
    return {"is_indexed": total_meters > 0, "total_meters": total_meters, "last_sync": metadata}

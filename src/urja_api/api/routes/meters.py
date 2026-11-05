import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from src.urja_api.api.dependencies import get_meter_service, get_repository
from src.urja_api.models.common import PaginatedResponse
from src.urja_api.models.meter import MeterDetail, MeterSummary
from src.urja_api.services.meter_service import MeterService
from src.urja_api.storage.repository import MeterRepository

router = APIRouter(prefix="/api/v1/meters", tags=["Meters"])


@router.get(
    "",
    response_model=PaginatedResponse[MeterSummary],
    summary="List and filter smart meters",
    description="Retrieve a paginated collection of smart meters with optional filtering, sorting, and geospatial radius search.",
)
async def list_meters(
    response: Response,
    q: Optional[str] = Query(None, description="Search substring against meterId or serialNo (e.g. J1000 or SE33)."),
    make: Optional[str] = Query(None, description="Filter by manufacturer (e.g. HPL, Genus, Secure, L&T, Allied)."),
    status: Optional[str] = Query(
        None, alias="install_status", description="Filter by status (Installed, Faulty, Decommissioned)."
    ),
    phase: Optional[str] = Query(None, alias="phase_type", description="Filter by phase (single, three)."),
    dt_code: Optional[str] = Query(None, description="Filter by Distribution Transformer code (e.g. DT-001)."),
    feeder_code: Optional[str] = Query(None, description="Filter by 11kV Feeder code (e.g. F-001)."),
    near_lat: Optional[float] = Query(
        None, ge=-90.0, le=90.0, description="Latitude for spatial radius query (WGS 84)."
    ),
    near_lng: Optional[float] = Query(
        None, ge=-180.0, le=180.0, description="Longitude for spatial radius query (WGS 84)."
    ),
    radius_km: Optional[float] = Query(
        None, gt=0.0, le=500.0, description="Search radius in kilometers around (near_lat, near_lng)."
    ),
    sort_by: str = Query(
        "meter_id", description="Sort attribute: meter_id, serial_number, make, install_status, phase_type."
    ),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order: asc or desc."),
    page: int = Query(1, ge=1, description="Page index (1-based)."),
    limit: int = Query(20, ge=1, le=200, description="Number of records per page (max 200)."),
    meter_service: MeterService = Depends(get_meter_service),
    repo: MeterRepository = Depends(get_repository),
):
    meters, pagination = await meter_service.list_meters(
        query=q,
        make=make,
        install_status=status,
        phase_type=phase,
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

    # Cache & freshness headers
    sync_meta = await repo.get_sync_metadata("meters_bulk")
    if sync_meta:
        response.headers["X-Data-Fetched-At"] = sync_meta["last_synced_at"]
        response.headers["X-Cache"] = "HIT"
    else:
        response.headers["X-Data-Fetched-At"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        response.headers["X-Cache"] = "MISS"

    # Aggregate data quality warnings across page items
    all_warnings = []
    for m in meters:
        all_warnings.extend(m.data_quality_warnings)

    return PaginatedResponse(data=meters, pagination=pagination, data_quality_warnings=all_warnings)


@router.get(
    "/{meter_id}",
    response_model=MeterDetail,
    summary="Get single meter detail",
    description="Look up full meter specifications, nameplate attributes, coordinates, and network hierarchy by meter ID.",
)
async def get_meter(
    meter_id: str,
    response: Response,
    meter_service: MeterService = Depends(get_meter_service),
    repo: MeterRepository = Depends(get_repository),
):
    meter = await meter_service.get_meter(meter_id)

    sync_meta = await repo.get_sync_metadata("meters_bulk")
    if sync_meta:
        response.headers["X-Data-Fetched-At"] = sync_meta["last_synced_at"]
        response.headers["X-Cache"] = "HIT"
    else:
        response.headers["X-Data-Fetched-At"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        response.headers["X-Cache"] = "MISS"

    return meter

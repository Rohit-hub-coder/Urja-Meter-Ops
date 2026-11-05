import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from src.urja_api.api.dependencies import get_portal_client, get_repository
from src.urja_api.client.portal_client import UrjaPortalClient
from src.urja_api.config import settings
from src.urja_api.models.health import CacheFreshness, HealthResponse, PortalReachability
from src.urja_api.storage.repository import MeterRepository

router = APIRouter(tags=["Health"])


@router.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Service health and upstream reachability check",
    description="Reports the live operational health of the API service, reachability and latency of the upstream Urja portal, and local database cache freshness.",
)
@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def check_health(
    portal_client: UrjaPortalClient = Depends(get_portal_client), repo: MeterRepository = Depends(get_repository)
):
    # Check portal reachability
    portal_info = await portal_client.check_health()
    portal_reachability = PortalReachability(
        is_reachable=portal_info["is_reachable"],
        http_status=portal_info["http_status"],
        latency_ms=portal_info["latency_ms"],
        error_message=portal_info["error_message"],
    )

    # Check cache status
    total_meters = await repo.get_total_meters_count()
    sync_meta = await repo.get_sync_metadata("meters_bulk")

    cache_age = None
    is_stale = False
    last_sync_dt = None

    if sync_meta and sync_meta.get("last_synced_at"):
        try:
            last_sync_dt = datetime.fromisoformat(sync_meta["last_synced_at"])
            cache_age = round(time.time() - last_sync_dt.timestamp(), 1)
            is_stale = cache_age > settings.cache_ttl_meters_sec
        except Exception:
            pass

    cache_freshness = CacheFreshness(
        is_cached=(total_meters > 0),
        total_meters_indexed=total_meters,
        last_sync_timestamp=last_sync_dt,
        cache_age_seconds=cache_age,
        is_stale=is_stale,
    )

    # Determine overall status
    if portal_reachability.is_reachable and total_meters > 0 and not is_stale:
        overall_status = "healthy"
    elif portal_reachability.is_reachable and (total_meters == 0 or is_stale):
        overall_status = "degraded"
    elif not portal_reachability.is_reachable and total_meters > 0:
        overall_status = "degraded"  # Can still serve cached responses
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        service_name="urja-meter-ops-api",
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        portal=portal_reachability,
        cache=cache_freshness,
    )

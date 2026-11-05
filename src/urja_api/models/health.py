from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CacheFreshness(BaseModel):
    is_cached: bool = Field(..., description="Whether local database/cache has synchronized data.")
    total_meters_indexed: int = Field(default=0, description="Total meters currently indexed in SQLite.")
    last_sync_timestamp: Optional[datetime] = Field(None, description="ISO timestamp of last successful bulk sync.")
    cache_age_seconds: Optional[float] = Field(None, description="Seconds elapsed since last sync.")
    is_stale: bool = Field(default=False, description="True if cache age exceeds configured TTL.")


class PortalReachability(BaseModel):
    is_reachable: bool = Field(..., description="Whether upstream portal responded successfully.")
    http_status: Optional[int] = Field(None, description="HTTP status code received from upstream.")
    latency_ms: Optional[float] = Field(None, description="Round-trip latency to upstream portal in milliseconds.")
    error_message: Optional[str] = Field(None, description="Error details if unreachable.")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall service status: healthy, degraded, unhealthy.")
    service_name: str = Field(default="urja-meter-ops-api", description="Service identifier.")
    environment: str = Field(default="development", description="Runtime environment.")
    timestamp: datetime = Field(..., description="Current system timestamp (ISO-8601).")
    portal: PortalReachability = Field(..., description="Upstream portal health & reachability.")
    cache: CacheFreshness = Field(..., description="Local storage index & cache freshness.")

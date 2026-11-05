import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from src.urja_api.api.dependencies import get_energy_service
from src.urja_api.errors import AppException
from src.urja_api.models.consumption import MeterConsumptionResponse
from src.urja_api.services.energy_service import EnergyService

router = APIRouter(prefix="/api/v1/meters", tags=["Consumption"])


@router.get(
    "/{meter_id}/consumption",
    response_model=MeterConsumptionResponse,
    summary="Get meter energy telemetry",
    description="Retrieve half-hourly interval load survey readings, cumulative registers (kWh, kVAh), voltage, and calculated window consumption.",
)
async def get_meter_consumption(
    meter_id: str,
    response: Response,
    from_date: Optional[datetime] = Query(
        None, description="Start date/timestamp boundary (e.g. 2026-06-25 or 2026-06-25T00:00:00)."
    ),
    to_date: Optional[datetime] = Query(None, description="End date/timestamp boundary (e.g. 2026-06-28)."),
    energy_service: EnergyService = Depends(get_energy_service),
):
    if from_date and to_date and from_date > to_date:
        raise AppException(
            status_code=422,
            title="Invalid Date Range",
            detail="Query parameter 'from_date' cannot be chronologically after 'to_date'.",
            code="INVALID_DATE_RANGE",
        )

    consumption = await energy_service.get_meter_consumption(meter_id=meter_id, from_dt=from_date, to_dt=to_date)

    response.headers["X-Data-Fetched-At"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    response.headers["X-Cache"] = "SWR"
    return consumption

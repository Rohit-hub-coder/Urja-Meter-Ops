from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.urja_api.models.common import DataQualityWarning


class TelemetryReading(BaseModel):
    timestamp_iso: datetime = Field(
        ..., description="Reading timestamp normalized to ISO-8601 with explicit timezone (IST +05:30)."
    )
    cumulative_active_energy_kwh: float = Field(
        ..., description="Cumulative active energy register reading in kilowatt-hours (kWh)."
    )
    cumulative_apparent_energy_kvah: float = Field(
        ..., description="Cumulative apparent energy register reading in kilovolt-ampere-hours (kVAh)."
    )
    voltage_phase_r_volts: float = Field(..., description="Phase R voltage in Volts (V).")
    interval_active_energy_kwh: Optional[float] = Field(
        None,
        description="Incremental active energy consumed during this interval in kWh (delta from previous reading).",
    )


class ConsumptionSummary(BaseModel):
    total_readings: int = Field(..., description="Number of telemetry readings in window.")
    start_time: Optional[datetime] = Field(None, description="Earliest reading timestamp in window.")
    end_time: Optional[datetime] = Field(None, description="Latest reading timestamp in window.")
    total_active_energy_consumed_kwh: Optional[float] = Field(
        None, description="Total active energy consumed over the queried window in kWh."
    )
    average_voltage_volts: Optional[float] = Field(
        None, description="Average Phase R voltage across the window in Volts."
    )
    min_voltage_volts: Optional[float] = Field(None, description="Minimum Phase R voltage recorded in Volts.")
    max_voltage_volts: Optional[float] = Field(None, description="Maximum Phase R voltage recorded in Volts.")


class MeterConsumptionResponse(BaseModel):
    meter_id: str = Field(..., description="Target meter identifier.")
    granularity: str = Field(default="30min", description="Interval granularity of telemetry data (e.g. 30min).")
    summary: ConsumptionSummary = Field(..., description="Aggregated metrics across the queried window.")
    readings: List[TelemetryReading] = Field(..., description="Ordered series of telemetry readings.")
    data_quality_warnings: List[DataQualityWarning] = Field(
        default_factory=list,
        description="Flags for anomalous telemetry (e.g. non-monotonic counter, sudden voltage drop).",
    )

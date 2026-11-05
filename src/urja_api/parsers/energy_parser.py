import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.urja_api.models.common import DataQualityWarning
from src.urja_api.models.consumption import (
    ConsumptionSummary,
    MeterConsumptionResponse,
    TelemetryReading,
)

# Indian Standard Time (IST) offset +05:30
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def parse_ist_timestamp(ts_str: str) -> datetime:
    """Parses legacy Indian format timestamp 'DD/MM/YYYY HH:MM' into timezone-aware IST datetime."""
    clean_ts = ts_str.strip()
    dt = datetime.strptime(clean_ts, "%d/%m/%Y %H:%M")
    return dt.replace(tzinfo=IST_TZ)


def parse_energy_telemetry(
    meter_id: str,
    raw_readings: List[Dict[str, Any]],
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
) -> MeterConsumptionResponse:
    """
    Parses and normalizes raw portal telemetry readings array into a strongly-typed,
    timezone-aware series with calculated interval consumption and aggregated summary.
    Handles:
    - Counter regressions/resets (flags warning, sets interval delta to None)
    - Missing intervals / telemetry gaps (flags warning)
    - Duplicate timestamps (flags warning, deduplicates)
    - First reading in window (interval_active_energy_kwh is None)
    """
    warnings: List[DataQualityWarning] = []
    parsed_readings: List[TelemetryReading] = []

    # 1. Parse and sort raw readings chronologically
    sorted_raw = []
    seen_timestamps = set()
    for item in raw_readings:
        try:
            dt = parse_ist_timestamp(str(item.get("timestamp", "")))
            if dt in seen_timestamps:
                warnings.append(
                    DataQualityWarning(
                        field="timestamp",
                        message=f"Duplicate reading timestamp '{dt.isoformat()}' on meter {meter_id}; skipped duplicate.",
                        severity="warning",
                        raw_value=str(item.get("timestamp")),
                    )
                )
                continue
            seen_timestamps.add(dt)
            sorted_raw.append((dt, item))
        except (ValueError, TypeError) as e:
            warnings.append(
                DataQualityWarning(
                    field="timestamp",
                    message=f"Malformed timestamp '{item.get('timestamp')}': {e}",
                    severity="warning",
                    raw_value=str(item.get("timestamp")),
                )
            )

    sorted_raw.sort(key=lambda x: x[0])

    # 2. Determine median interval granularity
    granularity = "30min"
    expected_step_minutes = 30
    if len(sorted_raw) >= 2:
        intervals = [
            (sorted_raw[i][0] - sorted_raw[i - 1][0]).total_seconds() / 60.0 for i in range(1, len(sorted_raw))
        ]
        median_minutes = statistics.median(intervals)
        if 20 <= median_minutes <= 40:
            granularity = "30min"
            expected_step_minutes = 30
        elif 1300 <= median_minutes <= 1500:
            granularity = "daily"
            expected_step_minutes = 1440
        else:
            granularity = f"{int(median_minutes)}min"
            expected_step_minutes = int(median_minutes)

    prev_dt: Optional[datetime] = None
    prev_kwh: Optional[float] = None

    for dt, item in sorted_raw:
        # Apply sub-day timestamp boundary filter if provided
        if from_dt and dt < from_dt:
            continue
        if to_dt and dt > to_dt:
            continue

        try:
            kwh = float(item.get("kwh", 0.0))
            kvah = float(item.get("kvah", 0.0))
            volt_r = float(item.get("voltR", 0.0))
        except (ValueError, TypeError) as e:
            warnings.append(
                DataQualityWarning(
                    field="readings", message=f"Non-numeric telemetry at {dt.isoformat()}: {e}", severity="error"
                )
            )
            continue

        # Check for gap relative to expected cadence
        if prev_dt is not None:
            gap_minutes = (dt - prev_dt).total_seconds() / 60.0
            if gap_minutes > (expected_step_minutes * 1.5):
                warnings.append(
                    DataQualityWarning(
                        field="timestamp_gap",
                        message=(
                            f"Telemetry gap of {int(gap_minutes)} minutes detected between "
                            f"{prev_dt.strftime('%d/%m/%Y %H:%M')} and {dt.strftime('%d/%m/%Y %H:%M')} "
                            f"(expected cadence: ~{expected_step_minutes}m)."
                        ),
                        severity="info",
                        raw_value=f"gap_minutes={gap_minutes}",
                    )
                )

        # Calculate incremental active energy delta
        interval_delta: Optional[float] = None
        if prev_kwh is not None:
            delta = round(kwh - prev_kwh, 4)
            if delta < 0:
                warnings.append(
                    DataQualityWarning(
                        field="cumulative_active_energy_kwh",
                        message=f"Counter regression or meter reset detected at {dt.isoformat()}: {prev_kwh} -> {kwh}.",
                        severity="warning",
                        raw_value=f"prev={prev_kwh},curr={kwh}",
                    )
                )
                interval_delta = None
            else:
                interval_delta = delta

        prev_kwh = kwh
        prev_dt = dt

        parsed_readings.append(
            TelemetryReading(
                timestamp_iso=dt,
                cumulative_active_energy_kwh=kwh,
                cumulative_apparent_energy_kvah=kvah,
                voltage_phase_r_volts=volt_r,
                interval_active_energy_kwh=interval_delta,
            )
        )

    # Compute aggregate summary
    if parsed_readings:
        start_time = parsed_readings[0].timestamp_iso
        end_time = parsed_readings[-1].timestamp_iso
        voltages = [r.voltage_phase_r_volts for r in parsed_readings if r.voltage_phase_r_volts > 0]
        avg_volt = round(sum(voltages) / len(voltages), 2) if voltages else None
        min_volt = min(voltages) if voltages else None
        max_volt = max(voltages) if voltages else None

        valid_intervals = [
            r.interval_active_energy_kwh for r in parsed_readings if r.interval_active_energy_kwh is not None
        ]
        total_kwh_consumed = round(sum(valid_intervals), 4) if valid_intervals else 0.0

        summary = ConsumptionSummary(
            total_readings=len(parsed_readings),
            start_time=start_time,
            end_time=end_time,
            total_active_energy_consumed_kwh=total_kwh_consumed,
            average_voltage_volts=avg_volt,
            min_voltage_volts=min_volt,
            max_voltage_volts=max_volt,
        )
    else:
        summary = ConsumptionSummary(
            total_readings=0,
            start_time=None,
            end_time=None,
            total_active_energy_consumed_kwh=0.0,
            average_voltage_volts=None,
            min_voltage_volts=None,
            max_voltage_volts=None,
        )

    return MeterConsumptionResponse(
        meter_id=meter_id,
        granularity=granularity,
        summary=summary,
        readings=parsed_readings,
        data_quality_warnings=warnings,
    )

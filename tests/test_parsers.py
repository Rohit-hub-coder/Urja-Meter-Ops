import json
from datetime import timedelta

from src.urja_api.models.meter import InstallStatus, PhaseType
from src.urja_api.parsers.energy_parser import parse_energy_telemetry, parse_ist_timestamp
from src.urja_api.parsers.meter_parser import (
    parse_coordinates,
    parse_meter_detail_from_html,
    parse_meter_from_export,
)


def test_parse_ist_timestamp():
    dt = parse_ist_timestamp("24/06/2026 00:30")
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 24
    assert dt.hour == 0
    assert dt.minute == 30
    assert dt.tzinfo is not None
    # Offset is +05:30
    assert dt.utcoffset() == timedelta(hours=5, minutes=30)


def test_parse_meter_from_export_sample():
    with open("tests/fixtures/portal_export.json") as f:
        data = json.load(f)
    meters_raw = data["data"]
    assert len(meters_raw) == 403

    # Test first meter J100000
    m0 = parse_meter_from_export(meters_raw[0])
    assert m0.meter_id == "J100000"
    assert m0.serial_number == "SE33962"
    assert m0.make == "HPL"
    assert m0.phase_type == PhaseType.SINGLE
    assert m0.install_status == InstallStatus.DECOMMISSIONED
    assert m0.dt_code == "DT-001"
    assert m0.location is not None
    assert round(m0.location.latitude, 2) == 26.94
    assert round(m0.location.longitude, 2) == 75.83
    assert m0.hierarchy.dt.code == "DT-001"
    assert m0.hierarchy.zone.code == "Z-01"


def test_parse_all_403_meters_from_export():
    with open("tests/fixtures/portal_export.json") as f:
        data = json.load(f)
    meters = [parse_meter_from_export(m) for m in data["data"]]
    assert len(meters) == 403

    # All meters should have valid locations
    assert all(m.location is not None for m in meters)
    # Check that the 22 partial hierarchy meters received DataQualityWarnings and were repaired
    meters_with_warnings = [m for m in meters if any("Inferred" in w.message for w in m.data_quality_warnings)]
    assert len(meters_with_warnings) == 22

    # Verify specifically on J100011 that raw values are preserved and not overwritten
    m11 = next(m for m in meters if m.meter_id == "J100011")
    assert m11.hierarchy.circle.code == "C-06"
    assert m11.hierarchy.circle.raw_code == ""
    assert m11.hierarchy.circle.name == "Circle 6"
    assert m11.hierarchy.circle.raw_name == "Circle 6"
    assert m11.hierarchy.circle.is_inferred is True


def test_parse_energy_telemetry_fixture():
    with open("tests/fixtures/meter_energy.json") as f:
        data = json.load(f)
    readings_raw = data["data"]
    assert len(readings_raw) == 337

    resp = parse_energy_telemetry("J100000", readings_raw)
    assert resp.meter_id == "J100000"
    assert resp.granularity == "30min"
    assert len(resp.readings) == 337
    assert resp.summary.total_readings == 337
    assert resp.summary.total_active_energy_consumed_kwh > 0
    assert 200.0 <= resp.summary.average_voltage_volts <= 250.0
    assert resp.summary.min_voltage_volts <= resp.summary.max_voltage_volts

    # Check first interval delta calculation
    assert resp.readings[0].interval_active_energy_kwh is None
    assert resp.readings[1].interval_active_energy_kwh is not None
    assert resp.readings[1].interval_active_energy_kwh > 0


def test_parse_meter_detail_from_html_fixture():
    with open("tests/fixtures/meter_detail_page.html") as f:
        html_text = f.read()

    detail = parse_meter_detail_from_html(html_text, "J100000")
    assert detail.meter_id == "J100000"
    assert detail.serial_number == "SE33962"
    assert detail.make == "HPL"
    assert detail.phase_type == PhaseType.SINGLE
    assert detail.install_status == InstallStatus.DECOMMISSIONED
    assert "Meter ID" in detail.nameplate_attributes


def test_swapped_coordinates_autocorrection():
    raw_geo = {"lat": 75.83, "lng": 26.93}
    loc, warns = parse_coordinates(raw_geo, "TEST_METER")
    assert loc is not None
    assert loc.latitude == 26.93
    assert loc.longitude == 75.83
    assert len(warns) == 1
    assert "Swapped" in warns[0].message


def test_invalid_coordinates():
    raw_geo = {"lat": "invalid", "lng": None}
    loc, warns = parse_coordinates(raw_geo, "TEST_METER")
    assert loc is None
    assert len(warns) == 1


def test_consumption_counter_reset_and_negative_delta():
    readings = [
        {"timestamp": "24/06/2026 00:00", "kwh": "100.0", "kvah": "110.0", "voltR": "230"},
        {"timestamp": "24/06/2026 00:30", "kwh": "102.5", "kvah": "112.5", "voltR": "231"},
        {"timestamp": "24/06/2026 01:00", "kwh": "5.0", "kvah": "6.0", "voltR": "230"},  # Reset to 5.0
    ]
    resp = parse_energy_telemetry("M-TEST", readings)
    assert len(resp.readings) == 3
    assert resp.readings[0].interval_active_energy_kwh is None
    assert resp.readings[1].interval_active_energy_kwh == 2.5
    assert resp.readings[2].interval_active_energy_kwh == 0.0  # Clamped to 0 on regression
    warns = [w for w in resp.data_quality_warnings if "Counter regression" in w.message]
    assert len(warns) == 1


def test_consumption_duplicate_timestamps():
    readings = [
        {"timestamp": "24/06/2026 00:00", "kwh": "100.0", "kvah": "110.0", "voltR": "230"},
        {"timestamp": "24/06/2026 00:00", "kwh": "100.0", "kvah": "110.0", "voltR": "230"},  # Duplicate
        {"timestamp": "24/06/2026 00:30", "kwh": "101.0", "kvah": "111.0", "voltR": "230"},
    ]
    resp = parse_energy_telemetry("M-TEST", readings)
    assert len(resp.readings) == 2  # Deduplicated
    warns = [w for w in resp.data_quality_warnings if "Duplicate reading timestamp" in w.message]
    assert len(warns) == 1


def test_consumption_interval_gaps_and_daily_cadence():
    # 24-hour cadence (daily snapshots like meter J100050)
    daily_readings = [
        {"timestamp": "24/06/2026 00:00", "kwh": "100.0", "kvah": "110.0", "voltR": "230"},
        {"timestamp": "25/06/2026 00:00", "kwh": "112.0", "kvah": "122.0", "voltR": "230"},
        {"timestamp": "26/06/2026 00:00", "kwh": "124.0", "kvah": "134.0", "voltR": "230"},
    ]
    resp = parse_energy_telemetry("M-DAILY", daily_readings)
    assert resp.granularity == "daily"
    assert len(resp.readings) == 3
    assert resp.readings[1].interval_active_energy_kwh == 12.0

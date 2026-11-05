from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from src.urja_api.models.common import DataQualityWarning
from src.urja_api.models.meter import (
    GeoCoordinates,
    InstallStatus,
    MeterDetail,
    MeterSummary,
    PhaseType,
)
from src.urja_api.parsers.hierarchy_parser import parse_and_normalize_hierarchy


def parse_phase_type(raw_phase: Optional[str]) -> Tuple[PhaseType, Optional[DataQualityWarning]]:
    if not raw_phase:
        return PhaseType.UNKNOWN, DataQualityWarning(
            field="phase_type", message="Phase type is missing; defaulted to UNKNOWN."
        )
    p = raw_phase.strip().lower()
    if "single" in p:
        return PhaseType.SINGLE, None
    elif "three" in p:
        return PhaseType.THREE, None
    return PhaseType.UNKNOWN, DataQualityWarning(
        field="phase_type", message=f"Unrecognized phase type '{raw_phase}'; defaulted to UNKNOWN.", raw_value=raw_phase
    )


def parse_install_status(raw_status: Optional[str]) -> Tuple[InstallStatus, Optional[DataQualityWarning]]:
    if not raw_status:
        return InstallStatus.UNKNOWN, DataQualityWarning(
            field="install_status", message="Install status is missing; defaulted to UNKNOWN."
        )
    s = raw_status.strip().title()
    for status_enum in InstallStatus:
        if status_enum.value.lower() == s.lower():
            return status_enum, None
    return InstallStatus.UNKNOWN, DataQualityWarning(
        field="install_status",
        message=f"Unrecognized install status '{raw_status}'; defaulted to UNKNOWN.",
        raw_value=raw_status,
    )


def parse_coordinates(
    raw_geo: Optional[Dict[str, Any]], meter_id: str
) -> Tuple[Optional[GeoCoordinates], List[DataQualityWarning]]:
    warnings: List[DataQualityWarning] = []
    if not raw_geo:
        warnings.append(
            DataQualityWarning(field="location", message=f"Meter {meter_id} has no coordinates.", severity="warning")
        )
        return None, warnings

    raw_lat = raw_geo.get("lat") if "lat" in raw_geo else raw_geo.get("latitude")
    raw_lng = raw_geo.get("lng") if "lng" in raw_geo else raw_geo.get("longitude")

    if raw_lat is None or raw_lng is None:
        warnings.append(
            DataQualityWarning(
                field="location", message=f"Meter {meter_id} has null coordinate components.", severity="warning"
            )
        )
        return None, warnings

    try:
        lat = float(raw_lat)
        lng = float(raw_lng)
    except (ValueError, TypeError):
        warnings.append(
            DataQualityWarning(
                field="location",
                message=f"Meter {meter_id} coordinates non-numeric: ({raw_lat}, {raw_lng}).",
                severity="error",
                raw_value=f"{raw_lat},{raw_lng}",
            )
        )
        return None, warnings

    # Swapped lat/lng check: Rajasthan is around lat 26-27, lng 75-76
    if 70.0 <= lat <= 80.0 and 20.0 <= lng <= 35.0:
        lat, lng = lng, lat
        warnings.append(
            DataQualityWarning(
                field="location",
                message=f"Swapped latitude/longitude coordinates detected and auto-corrected for meter {meter_id}.",
                severity="warning",
                raw_value=f"{raw_lat},{raw_lng}",
            )
        )

    # Validate coordinate range
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        warnings.append(
            DataQualityWarning(
                field="location",
                message=f"Coordinates out of WGS84 range: ({lat}, {lng}).",
                severity="error",
                raw_value=f"{lat},{lng}",
            )
        )
        return None, warnings

    return GeoCoordinates(latitude=lat, longitude=lng), warnings


def parse_meter_from_export(raw: Dict[str, Any]) -> MeterSummary:
    """Parses a raw meter dictionary from the bulk export endpoint."""
    meter_id = str(raw.get("meterId", "")).strip()
    serial_number = str(raw.get("serialNo", "")).strip()
    make = str(raw.get("make", "")).strip()
    dt_code = str(raw.get("dtCode", "")).strip()

    phase_type, phase_warn = parse_phase_type(raw.get("phaseType"))
    install_status, status_warn = parse_install_status(raw.get("installStatus"))
    location, geo_warns = parse_coordinates(raw.get("geo"), meter_id)
    hierarchy, hier_warns = parse_and_normalize_hierarchy(raw.get("hierarchy"), meter_id)

    warnings: List[DataQualityWarning] = []
    if phase_warn:
        warnings.append(phase_warn)
    if status_warn:
        warnings.append(status_warn)
    warnings.extend(geo_warns)
    warnings.extend(hier_warns)

    return MeterSummary(
        meter_id=meter_id,
        serial_number=serial_number,
        make=make,
        phase_type=phase_type,
        install_status=install_status,
        install_type=raw.get("installType"),
        build_version=raw.get("build"),
        dt_code=dt_code,
        location=location,
        hierarchy=hierarchy,
        data_quality_warnings=warnings,
    )


def parse_meter_detail_from_html(html_text: str, meter_id: str) -> MeterDetail:
    """Fallback parser: extracts meter details from legacy server-rendered HTML page."""
    soup = BeautifulSoup(html_text, "html.parser")
    attributes: Dict[str, str] = {}

    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        key = dt.get_text(strip=True)
        val = dd.get_text(strip=True)
        if key:
            attributes[key] = val

    serial_number = attributes.get("Serial No", "")
    make = attributes.get("Make", "")
    raw_phase = attributes.get("Phase Type", "")
    raw_status = attributes.get("Installation Status", "")
    raw_type = attributes.get("Installation Type", "")

    phase_type, phase_warn = parse_phase_type(raw_phase)
    install_status, status_warn = parse_install_status(raw_status)

    warnings: List[DataQualityWarning] = []
    if phase_warn:
        warnings.append(phase_warn)
    if status_warn:
        warnings.append(status_warn)

    return MeterDetail(
        meter_id=meter_id,
        serial_number=serial_number,
        make=make,
        phase_type=phase_type,
        install_status=install_status,
        install_type=raw_type or None,
        dt_code="",
        location=None,
        hierarchy=None,
        nameplate_attributes=attributes,
        data_quality_warnings=warnings,
    )

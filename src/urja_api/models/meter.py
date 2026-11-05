from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from src.urja_api.models.common import DataQualityWarning


class PhaseType(str, Enum):
    SINGLE = "single"
    THREE = "three"
    UNKNOWN = "unknown"


class InstallStatus(str, Enum):
    INSTALLED = "Installed"
    FAULTY = "Faulty"
    DECOMMISSIONED = "Decommissioned"
    UNKNOWN = "Unknown"


class InstallType(str, Enum):
    WHOLE_CURRENT = "Whole Current"
    CT_OPERATED = "CT Operated"
    UNKNOWN = "Unknown"


class GeoCoordinates(BaseModel):
    latitude: float = Field(..., description="Latitude in decimal degrees (WGS 84).", ge=-90.0, le=90.0)
    longitude: float = Field(..., description="Longitude in decimal degrees (WGS 84).", ge=-180.0, le=180.0)
    distance_km: Optional[float] = Field(
        None, description="Distance from search origin in kilometers (if spatial query applied)."
    )


class MeterHierarchyNode(BaseModel):
    code: str = Field(..., description="Normalized entity identifier code.")
    name: str = Field(..., description="Normalized entity descriptive name.")
    raw_code: Optional[str] = Field(None, description="Original un-normalized code from upstream portal.")
    raw_name: Optional[str] = Field(None, description="Original un-normalized name from upstream portal.")
    is_inferred: bool = Field(default=False, description="True if either code or name was inferred from peer nodes.")


class MeterHierarchySummary(BaseModel):
    zone: Optional[MeterHierarchyNode] = Field(None, description="Discom Zone.")
    circle: Optional[MeterHierarchyNode] = Field(None, description="Distribution Circle.")
    division: Optional[MeterHierarchyNode] = Field(None, description="Operational Division.")
    subdivision: Optional[MeterHierarchyNode] = Field(None, description="Subdivision.")
    substation: Optional[MeterHierarchyNode] = Field(None, description="Distribution Substation.")
    feeder: Optional[MeterHierarchyNode] = Field(None, description="11kV Feeder.")
    dt: Optional[MeterHierarchyNode] = Field(None, description="Distribution Transformer.")


class MeterSummary(BaseModel):
    meter_id: str = Field(..., description="Unique meter identifier (e.g. J100000).")
    serial_number: str = Field(..., description="Manufacturer serial number (e.g. SE33962).")
    make: str = Field(..., description="Manufacturer make (e.g. HPL, Genus, Secure, L&T, Allied).")
    phase_type: PhaseType = Field(..., description="Meter electrical phase configuration.")
    install_status: InstallStatus = Field(..., description="Operational lifecycle status.")
    install_type: Optional[str] = Field(None, description="Metering category (e.g. Whole Current, CT Operated).")
    build_version: Optional[str] = Field(None, description="Meter hardware/firmware build (legacy, v2).")
    dt_code: str = Field(..., description="Associated Distribution Transformer code.")
    location: Optional[GeoCoordinates] = Field(None, description="Geographic location.")
    hierarchy: Optional[MeterHierarchySummary] = Field(None, description="Network topology positioning.")
    data_quality_warnings: List[DataQualityWarning] = Field(
        default_factory=list, description="Flags for anomalous or repaired attributes."
    )


class MeterDetail(MeterSummary):
    """Full meter representation with additional nameplate specifications."""

    nameplate_attributes: dict = Field(
        default_factory=dict, description="Extended nameplate specifications and parameters."
    )

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class DataQualityWarning(BaseModel):
    """Represents an anomaly or repair made to upstream data."""

    field: str = Field(..., description="The affected attribute or node level.")
    message: str = Field(..., description="Description of the quality issue.")
    severity: str = Field(default="warning", description="Severity level: info, warning, error.")
    raw_value: Optional[str] = Field(None, description="The unnormalized raw upstream value.")


class PaginationMetadata(BaseModel):
    total_records: int = Field(..., description="Total count of matching records.", ge=0)
    page: int = Field(..., description="Current page number (1-based).", ge=1)
    limit: int = Field(..., description="Number of records per page.", ge=1)
    total_pages: int = Field(..., description="Total pages available.", ge=0)
    has_next: bool = Field(..., description="True if next page exists.")
    has_prev: bool = Field(..., description="True if previous page exists.")


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T] = Field(..., description="List of items for current page.")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata.")
    data_quality_warnings: List[DataQualityWarning] = Field(
        default_factory=list, description="Any data quality issues or corrections applied."
    )

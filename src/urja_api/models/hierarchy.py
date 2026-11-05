from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from src.urja_api.models.common import DataQualityWarning


class NodeType(str, Enum):
    ZONE = "zone"
    CIRCLE = "circle"
    DIVISION = "division"
    SUBDIVISION = "subdivision"
    SUBSTATION = "substation"
    FEEDER = "feeder"
    DT = "dt"
    METER = "meter"


class TreeNode(BaseModel):
    id: str = Field(..., description="Unique code or ID for the topology node.")
    name: str = Field(..., description="Descriptive human-readable label.")
    type: NodeType = Field(..., description="Hierarchical tier type.")
    parent_id: Optional[str] = Field(None, description="Identifier of parent node.")
    meter_count: int = Field(default=0, description="Total meters connected under this subtree.", ge=0)
    capacity_kva: Optional[float] = Field(None, description="Transformer capacity in kVA (if type is DT).")
    children: List["TreeNode"] = Field(default_factory=list, description="Child nodes in the network topology.")


class AncestorNode(BaseModel):
    id: str = Field(..., description="Entity code or identifier.")
    name: str = Field(..., description="Entity name.")
    type: NodeType = Field(..., description="Hierarchy tier level.")


class NodeDetailView(BaseModel):
    id: str = Field(..., description="Requested entity code or ID.")
    name: str = Field(..., description="Entity name.")
    type: NodeType = Field(..., description="Hierarchy tier level.")
    capacity_kva: Optional[float] = Field(None, description="Transformer rating in kVA if DT.")
    meter_count: int = Field(..., description="Total meters directly or indirectly under this node.")
    ancestors: List[AncestorNode] = Field(..., description="Path from root zone down to parent.")
    children: List[AncestorNode] = Field(..., description="Immediate child nodes.")
    data_quality_warnings: List[DataQualityWarning] = Field(
        default_factory=list, description="Flags for anomalous parent links or repaired topology values."
    )


class NetworkHierarchyResponse(BaseModel):
    total_nodes: int = Field(..., description="Total nodes across all tiers.")
    total_meters: int = Field(..., description="Total operational meters mapped in topology.")
    root_zones: List[TreeNode] = Field(..., description="Top-level utility zones.")
    data_quality_warnings: List[DataQualityWarning] = Field(
        default_factory=list, description="Warnings for repaired or missing parent/code relationships."
    )

from fastapi import APIRouter, Depends

from src.urja_api.api.dependencies import get_hierarchy_service, get_repository
from src.urja_api.errors import NotFoundError
from src.urja_api.models.hierarchy import NetworkHierarchyResponse, NodeDetailView
from src.urja_api.services.hierarchy_service import HierarchyService
from src.urja_api.storage.repository import MeterRepository

router = APIRouter(prefix="/api/v1/hierarchy", tags=["Hierarchy"])


@router.get(
    "",
    response_model=NetworkHierarchyResponse,
    summary="Get complete distribution network tree",
    description="Returns the full 7-tier distribution network hierarchy (Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT) with meter count rollups at every node.",
)
async def get_network_tree(hierarchy_service: HierarchyService = Depends(get_hierarchy_service)):
    return await hierarchy_service.get_network_tree()


@router.get(
    "/nodes/{node_id}",
    response_model=NodeDetailView,
    summary="Get hierarchy node detail view",
    description="Inspect a specific node in the network hierarchy (e.g. DT or Feeder) with its full ancestor path from the root Zone down to parent, immediate children, and meter count.",
)
async def get_node_detail(node_id: str, repo: MeterRepository = Depends(get_repository)):
    node_view = await repo.get_node_detail(node_id)
    if not node_view:
        raise NotFoundError("Hierarchy node", node_id)
    return node_view

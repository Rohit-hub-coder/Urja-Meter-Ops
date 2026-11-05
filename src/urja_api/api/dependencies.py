from src.urja_api.client.portal_client import UrjaPortalClient
from src.urja_api.services.energy_service import EnergyService
from src.urja_api.services.hierarchy_service import HierarchyService
from src.urja_api.services.meter_service import MeterService
from src.urja_api.services.sync_service import SyncService
from src.urja_api.storage.repository import MeterRepository

# Shared singleton client instances for connection pooling
_portal_client = UrjaPortalClient()
_repository = MeterRepository()
_sync_service = SyncService(_portal_client, _repository)
_meter_service = MeterService(_repository, _portal_client, _sync_service)
_energy_service = EnergyService(_portal_client)
_hierarchy_service = HierarchyService()


def get_portal_client() -> UrjaPortalClient:
    return _portal_client


def get_repository() -> MeterRepository:
    return _repository


def get_sync_service() -> SyncService:
    return _sync_service


def get_meter_service() -> MeterService:
    return _meter_service


def get_energy_service() -> EnergyService:
    return _energy_service


def get_hierarchy_service() -> HierarchyService:
    return _hierarchy_service

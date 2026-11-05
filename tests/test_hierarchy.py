import aiosqlite
import pytest

from src.urja_api.models.hierarchy import NodeType
from src.urja_api.models.meter import GeoCoordinates, InstallStatus, MeterSummary, PhaseType
from src.urja_api.parsers.hierarchy_parser import parse_and_normalize_hierarchy
from src.urja_api.services.hierarchy_service import HierarchyService
from src.urja_api.storage.database import SCHEMA_SQL
from src.urja_api.storage.repository import MeterRepository


@pytest.fixture
async def temp_db(tmp_path):
    db_file = tmp_path / "test_hierarchy.db"
    async with aiosqlite.connect(str(db_file)) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    return str(db_file)


@pytest.mark.asyncio
async def test_hierarchy_tree_reconstruction_with_rollups(temp_db, monkeypatch):
    from src.urja_api.config import settings

    monkeypatch.setattr(settings, "database_path", temp_db)

    repo = MeterRepository()
    # Insert DT
    await repo.upsert_transformers(
        [{"code": "DT-101", "name": "Test DT 101", "feederCode": "F-001", "capacityKva": 250.0}]
    )

    # Insert 3 meters under DT-101
    meters = []
    for i in range(3):
        h, warns = parse_and_normalize_hierarchy(
            {
                "zone": {"code": "Z-01", "name": "Zone 1"},
                "circle": {"code": "C-01", "name": "Circle 1"},
                "division": {"code": "D-01", "name": "Division 1"},
                "subdivision": {"code": "SD-01", "name": "Subdivision 1"},
                "substation": {"code": "SS-01", "name": "Substation 1"},
                "feeder": {"code": "F-001", "name": "Feeder 1"},
                "dt": {"code": "DT-101", "name": "Test DT 101"},
            },
            f"M-{i}",
        )
        meters.append(
            MeterSummary(
                meter_id=f"M-{i}",
                serial_number=f"SN-{i}",
                make="HPL",
                phase_type=PhaseType.SINGLE,
                install_status=InstallStatus.INSTALLED,
                dt_code="DT-101",
                location=GeoCoordinates(latitude=26.91, longitude=75.78),
                hierarchy=h,
            )
        )
    await repo.upsert_meters(meters)

    service = HierarchyService()
    tree_resp = await service.get_network_tree()

    assert tree_resp.total_meters == 3
    assert len(tree_resp.root_zones) == 1
    zone = tree_resp.root_zones[0]
    assert zone.id == "Z-01"
    assert zone.meter_count == 3
    assert len(zone.children) == 1  # Circle

    circle = zone.children[0]
    assert circle.id == "C-01"
    assert circle.meter_count == 3

    # Navigate to DT
    division = circle.children[0]
    subdiv = division.children[0]
    substation = subdiv.children[0]
    feeder = substation.children[0]
    dt = feeder.children[0]
    assert dt.id == "DT-101"
    assert dt.type == NodeType.DT
    assert dt.meter_count == 3
    assert dt.capacity_kva == 250.0


@pytest.mark.asyncio
async def test_hierarchy_messy_data_handling(temp_db, monkeypatch):
    from src.urja_api.config import settings

    monkeypatch.setattr(settings, "database_path", temp_db)

    # Meter with empty circle code but present name: 'Circle 6'
    # Should infer code 'C-06' and add a DataQualityWarning
    raw_h = {
        "zone": {"code": "Z-03", "name": "Jaipur Zone 3"},
        "circle": {"code": "", "name": "Circle 6"},
        "division": {"code": "D-02", "name": "Division 2"},
        "subdivision": {"code": "SD-12", "name": "Subdivision 12"},
        "substation": {"code": "SS-12", "name": "Substation 12"},
        "feeder": {"code": "F-012", "name": "Feeder 12"},
        "dt": {"code": "DT-012", "name": "Mansarovar DT 12"},
    }
    h_summary, warns = parse_and_normalize_hierarchy(raw_h, "J100011")
    assert h_summary.circle.code == "C-06"
    assert h_summary.circle.name == "Circle 6"
    assert h_summary.circle.raw_code == ""
    assert h_summary.circle.raw_name == "Circle 6"
    assert h_summary.circle.is_inferred is True
    assert len(warns) == 1
    assert "Inferred missing code 'C-06'" in warns[0].message

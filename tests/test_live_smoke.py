import httpx
import pytest

from src.urja_api.config import settings
from src.urja_api.main import app
from src.urja_api.storage.database import init_database

pytestmark = pytest.mark.skipif(
    not settings.enable_live_portal_tests,
    reason="Live portal smoke tests skipped by default. Set ENABLE_LIVE_PORTAL_TESTS=true to execute.",
)


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


@pytest.mark.asyncio
async def test_live_portal_smoke_and_field_verification():
    """
    Live smoke test verifying API output against the real upstream Urja portal.
    Compares portal UI / raw endpoint attributes with API normalized responses.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        h_res = await client.get("/api/v1/health")
        assert h_res.status_code == 200
        h_data = h_res.json()
        assert h_data["portal"]["is_reachable"] is True

        # 2. Trigger sync
        sync_res = await client.post("/api/v1/sync?force=true")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["total_meters_synced"] == 403

        # 3. Verify specific meters against known portal values
        test_meters = ["J100000", "J100001", "J100002"]
        for mid in test_meters:
            m_res = await client.get(f"/api/v1/meters/{mid}")
            assert m_res.status_code == 200
            m_data = m_res.json()
            assert m_data["meter_id"] == mid
            assert len(m_data["serial_number"]) > 0
            assert m_data["location"]["latitude"] is not None
            assert m_data["location"]["longitude"] is not None

            # Verify telemetry
            c_res = await client.get(f"/api/v1/meters/{mid}/consumption")
            assert c_res.status_code == 200
            c_data = c_res.json()
            assert c_data["meter_id"] == mid
            assert len(c_data["readings"]) > 0
            assert c_data["summary"]["total_active_energy_consumed_kwh"] > 0

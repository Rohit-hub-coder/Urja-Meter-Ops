import json
import time

import httpx
import pytest
import respx

from src.urja_api.config import settings
from src.urja_api.main import app
from src.urja_api.parsers.meter_parser import parse_meter_from_export
from src.urja_api.storage.database import init_database
from src.urja_api.storage.repository import MeterRepository


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_api.db"
    monkeypatch.setattr(settings, "database_path", str(db_file))
    await init_database()

    # Pre-populate with fixtures
    with open("tests/fixtures/portal_export.json") as f:
        export_data = json.load(f)
    meters = [parse_meter_from_export(m) for m in export_data["data"]]

    with open("tests/fixtures/portal_dts_page1.json") as f:
        dts_data = json.load(f)["data"]

    repo = MeterRepository()
    await repo.upsert_transformers(dts_data)
    await repo.upsert_meters(meters)
    await repo.record_sync_metadata("meters_bulk", len(meters), "success")


@pytest.mark.asyncio
async def test_list_meters_happy_path():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/meters?page=1&limit=10")
        assert res.status_code == 200
        data = res.json()
        assert len(data["data"]) == 10
        assert data["pagination"]["total_records"] == 403
        assert data["pagination"]["total_pages"] == 41
        assert data["pagination"]["page"] == 1
        assert "X-Cache" in res.headers
        assert res.headers["X-Cache"] == "HIT"


@pytest.mark.asyncio
async def test_filter_meters_by_make_and_status():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/meters?make=HPL&install_status=Installed")
        assert res.status_code == 200
        data = res.json()
        assert all(m["make"] == "HPL" for m in data["data"])
        assert all(m["install_status"] == "Installed" for m in data["data"])


@pytest.mark.asyncio
async def test_spatial_radius_search():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Search near Jaipur center: Lat 26.9124, Lng 75.7873 within 5 km
        res = await client.get("/api/v1/meters?near_lat=26.9124&near_lng=75.7873&radius_km=5.0")
        assert res.status_code == 200
        data = res.json()
        assert len(data["data"]) > 0
        # All returned meters must have distance_km <= 5.0
        for m in data["data"]:
            assert m["location"]["distance_km"] is not None
            assert m["location"]["distance_km"] <= 5.0
        # Distance must be sorted ascending
        distances = [m["location"]["distance_km"] for m in data["data"]]
        assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_get_meter_detail_found():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/meters/J100000")
        assert res.status_code == 200
        m = res.json()
        assert m["meter_id"] == "J100000"
        assert m["serial_number"] == "SE33962"
        assert m["make"] == "HPL"
        assert m["hierarchy"]["zone"]["code"] == "Z-01"


@pytest.mark.asyncio
async def test_get_meter_not_found_rfc7807():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/meters/NONEXISTENT_METER_999")
        assert res.status_code == 404
        assert res.headers["content-type"] == "application/problem+json"
        problem = res.json()
        assert problem["status"] == 404
        assert problem["title"] == "Resource Not Found"
        assert "NONEXISTENT_METER_999" in problem["detail"]


@pytest.mark.asyncio
@respx.mock
async def test_meter_consumption_endpoint():
    # Mock portal login for fresh sessions
    respx.post(f"{settings.portal_base_url}/login").respond(
        status_code=200, headers={"set-cookie": "__Secure-better-auth.session_token=test_token; Path=/"}
    )

    # Mock portal upstream energy endpoint
    with open("tests/fixtures/meter_energy.json") as f:
        energy_fixture = json.load(f)

    respx.get(f"{settings.portal_base_url}/portal/meters/J100000/energy").respond(status_code=200, json=energy_fixture)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/meters/J100000/consumption")
        assert res.status_code == 200
        data = res.json()
        assert data["meter_id"] == "J100000"
        assert data["granularity"] == "30min"
        assert len(data["readings"]) == 337
        assert data["summary"]["total_active_energy_consumed_kwh"] > 0
        assert data["summary"]["average_voltage_volts"] > 200.0


@pytest.mark.asyncio
async def test_hierarchy_tree_endpoint():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/hierarchy")
        assert res.status_code == 200
        data = res.json()
        assert data["total_meters"] == 403
        assert len(data["root_zones"]) == 3
        # Check rollups
        total_zone_meters = sum(z["meter_count"] for z in data["root_zones"])
        assert total_zone_meters == 403


@pytest.mark.asyncio
async def test_hierarchy_node_detail_view():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/hierarchy/nodes/DT-001")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "DT-001"
        assert data["type"] == "dt"
        assert data["meter_count"] > 0
        assert len(data["children"]) == data["meter_count"]
        assert len(data["ancestors"]) > 0
        assert data["ancestors"][0]["type"] == "zone"


@pytest.mark.asyncio
@respx.mock
async def test_health_check_healthy():
    # Mock portal login check
    respx.get(f"{settings.portal_base_url}/login").respond(status_code=200)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["portal"]["is_reachable"] is True
        assert data["cache"]["is_cached"] is True
        assert data["cache"]["total_meters_indexed"] == 403


@pytest.mark.asyncio
@respx.mock
async def test_upstream_session_expiry_resilience():
    """Tests that a 302 silent redirect on expired session triggers automatic re-login."""
    from src.urja_api.client.auth import SessionManager
    from src.urja_api.client.portal_client import UrjaPortalClient

    sm = SessionManager()
    # Set an initial dummy token
    sm._session_token = "expired_token_abc"
    sm._token_expires_at = 9999999999.0

    p_client = UrjaPortalClient(session_manager=sm)

    # First energy call returns 302 -> /login
    route_energy = respx.get(f"{settings.portal_base_url}/portal/meters/J100000/energy")
    route_energy.side_effect = [
        httpx.Response(302, headers={"location": "/login"}),
        httpx.Response(
            200, json={"data": [{"timestamp": "24/06/2026 00:00", "kwh": "100.0", "kvah": "105.0", "voltR": "230"}]}
        ),
    ]

    # Re-login route
    respx.post(f"{settings.portal_base_url}/login").respond(
        status_code=200, headers={"set-cookie": "__Secure-better-auth.session_token=fresh_token_xyz; Path=/"}
    )

    res = await p_client.fetch_meter_energy("J100000")
    assert "data" in res
    assert len(res["data"]) == 1
    assert sm._session_token == "fresh_token_xyz"


@pytest.mark.asyncio
@respx.mock
async def test_upstream_502_error_mapping():
    """Tests that upstream 500/502 errors map to RFC 7807 502 Bad Gateway."""
    from src.urja_api.client.auth import SessionManager
    from src.urja_api.client.portal_client import UrjaPortalClient
    from src.urja_api.errors import UpstreamPortalError

    sm = SessionManager()
    sm._session_token = "valid_token"
    sm._token_expires_at = 9999999999.0

    p_client = UrjaPortalClient(session_manager=sm)
    # Mock persistent 502 from upstream
    respx.get(f"{settings.portal_base_url}/portal/meters/J100000/energy").respond(status_code=502)

    with pytest.raises(UpstreamPortalError) as exc_info:
        await p_client.fetch_meter_energy("J100000")
    assert exc_info.value.status_code == 502
    assert "Upstream portal returned HTTP 502" in exc_info.value.detail


@pytest.mark.asyncio
@respx.mock
async def test_export_secret_invalidation_and_retry_on_403():
    """Tests that a 403 on /portal/export invalidates the cached secret and retries once with fresh keys."""
    from src.urja_api.client.auth import SessionManager
    from src.urja_api.client.portal_client import UrjaPortalClient

    sm = SessionManager()
    sm._session_token = "valid_token"
    sm._token_expires_at = 9999999999.0
    sm._signing_secret = "stale_secret_123"
    sm._secret_fetched_at = time.time()

    p_client = UrjaPortalClient(session_manager=sm)

    # First call with stale secret returns 403; second call with fresh secret returns 200
    route_export = respx.get(f"{settings.portal_base_url}/portal/export")
    route_export.side_effect = [
        httpx.Response(403, json={"error": "invalid_signature"}),
        httpx.Response(200, json={"data": [{"meterId": "J100000", "serialNo": "SE33962"}], "total": 1}),
    ]

    # Keys endpoint returning fresh secret
    keys_route = respx.get(f"{settings.portal_base_url}/portal/keys").respond(
        status_code=200, json={"data": {"signingSecret": "fresh_secret_456"}}
    )

    data = await p_client.fetch_meters_bulk()
    assert len(data["data"]) == 1
    assert data["data"][0]["meterId"] == "J100000"
    assert keys_route.called
    assert sm._signing_secret == "fresh_secret_456"


@pytest.mark.asyncio
@respx.mock
async def test_export_fallback_to_paged_crawl_on_persistent_403(tmp_path, monkeypatch):
    """Tests that persistent 403/failure on /portal/export falls back to paged search crawl."""
    from src.urja_api.client.auth import SessionManager
    from src.urja_api.client.portal_client import UrjaPortalClient
    from src.urja_api.services.sync_service import SyncService

    # Use fresh db
    db_file = tmp_path / "test_fallback_sync.db"
    monkeypatch.setattr(settings, "database_path", str(db_file))
    await init_database()

    sm = SessionManager()
    sm._session_token = "valid_token"
    sm._token_expires_at = 9999999999.0
    sm._signing_secret = "secret"
    sm._secret_fetched_at = time.time()

    p_client = UrjaPortalClient(session_manager=sm)
    repo = MeterRepository()
    sync_service = SyncService(portal_client=p_client, repository=repo)

    # Keys endpoint
    respx.get(f"{settings.portal_base_url}/portal/keys").respond(
        status_code=200, json={"data": {"signingSecret": "fresh_secret"}}
    )

    # Persistent 403 on export (both attempts fail)
    respx.get(f"{settings.portal_base_url}/portal/export").respond(status_code=403, json={"error": "forbidden"})

    # DTs endpoint
    respx.get(f"{settings.portal_base_url}/portal/dts").respond(
        status_code=200,
        json={"data": [{"code": "DT-001", "name": "Test DT", "feederCode": "F-001", "capacityKva": 100}]},
    )

    # Paged search endpoint (fallback)
    respx.get(f"{settings.portal_base_url}/portal/meters/search").respond(
        status_code=200,
        json={
            "data": [
                {
                    "meterId": "J999001",
                    "serialNo": "GE12345",
                    "make": "Genus",
                    "phaseType": "single",
                    "installStatus": "Installed",
                    "dtCode": "DT-001",
                }
            ],
            "total": 1,
            "page": 1,
            "pageSize": 20,
        },
    )

    result = await sync_service.sync_all(force=True)
    assert result["status"] == "success"
    assert result["total_meters_synced"] == 1
    assert result["total_dts_synced"] == 1

    # Verify meter is queried in repo
    meters, meta = await repo.query_meters()
    assert meta.total_records == 1
    assert meters[0].meter_id == "J999001"
    assert meters[0].make == "Genus"


@pytest.mark.asyncio
@respx.mock
async def test_lifespan_startup_sync_on_empty_db(tmp_path, monkeypatch):
    """Tests that app lifespan auto-seeds SQLite cache if DB is empty on startup."""
    from src.urja_api.main import lifespan

    empty_db = tmp_path / "empty_startup.db"
    monkeypatch.setattr(settings, "database_path", str(empty_db))
    monkeypatch.setattr(settings, "portal_username", "mock_user@example.local")
    monkeypatch.setattr(settings, "portal_password", "mock_password_123")

    with open("tests/fixtures/portal_export.json") as f:
        export_data = json.load(f)
    with open("tests/fixtures/portal_dts_page1.json") as f:
        dts_data = json.load(f)

    # Mock login, export, dts, keys
    respx.post(f"{settings.portal_base_url}/login").respond(
        status_code=200, headers={"set-cookie": "__Secure-better-auth.session_token=test_tok; Path=/"}
    )
    respx.get(f"{settings.portal_base_url}/portal/keys").respond(
        status_code=200, json={"data": {"signingSecret": "secret_123"}}
    )
    respx.get(f"{settings.portal_base_url}/portal/export").respond(status_code=200, json=export_data)
    respx.get(f"{settings.portal_base_url}/portal/dts").respond(status_code=200, json=dts_data)

    async with lifespan(app):
        repo = MeterRepository()
        count = await repo.get_total_meters_count()
        assert count == 403


@pytest.mark.asyncio
@respx.mock
async def test_sync_cooldown_rate_limit_and_retry_after():
    """Tests that manual sync without force=true during cooldown returns 429 with Retry-After header."""
    from src.urja_api.api.dependencies import get_sync_service

    sync_service = get_sync_service()
    sync_service._last_sync_time = 0.0

    with open("tests/fixtures/portal_export.json") as f:
        export_data = json.load(f)
    with open("tests/fixtures/portal_dts_page1.json") as f:
        dts_data = json.load(f)

    respx.post(f"{settings.portal_base_url}/login").respond(
        status_code=200, headers={"set-cookie": "__Secure-better-auth.session_token=test_tok; Path=/"}
    )
    respx.get(f"{settings.portal_base_url}/portal/keys").respond(
        status_code=200, json={"data": {"signingSecret": "secret_123"}}
    )
    respx.get(f"{settings.portal_base_url}/portal/export").respond(status_code=200, json=export_data)
    respx.get(f"{settings.portal_base_url}/portal/dts").respond(status_code=200, json=dts_data)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # First sync succeeds
        r1 = await client.post("/api/v1/sync?force=true")
        assert r1.status_code == 200

        # Immediate second sync without force triggers 429
        r2 = await client.post("/api/v1/sync")
        assert r2.status_code == 429
        assert r2.headers.get("content-type") == "application/problem+json"
        assert "Retry-After" in r2.headers
        retry_after = int(r2.headers["Retry-After"])
        assert 0 < retry_after <= settings.sync_cooldown_sec
        body = r2.json()
        assert body["code"] == "RATE_LIMIT_EXCEEDED"
        assert body["status"] == 429


@pytest.mark.asyncio
async def test_get_ui_and_vendored_static_assets():
    """Tests that Web Console /ui and vendored static assets serve 200 OK offline."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Root and /ui serve HTML
        for path in ["/", "/ui"]:
            res = await client.get(path)
            assert res.status_code == 200
            assert "text/html" in res.headers["content-type"]
            assert "Urja Meter Ops" in res.text

        # Vendored assets exist and serve 200
        for asset in ["leaflet.css", "leaflet.js", "chart.umd.js", "tailwindcss.js"]:
            res = await client.get(f"/static/vendor/{asset}")
            assert res.status_code == 200
            assert len(res.content) > 1000


@pytest.mark.asyncio
async def test_pagination_bounds_validation():
    """Tests that out-of-bounds pagination parameters return 422 ProblemDetails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # page < 1
        r_page = await client.get("/api/v1/meters?page=0")
        assert r_page.status_code == 422
        assert r_page.headers.get("content-type") == "application/problem+json"
        p_page = r_page.json()
        assert p_page["code"] == "VALIDATION_ERROR"
        assert p_page["status"] == 422

        # limit < 1
        r_lim_low = await client.get("/api/v1/meters?limit=0")
        assert r_lim_low.status_code == 422
        assert r_lim_low.headers.get("content-type") == "application/problem+json"

        # limit > 200
        r_lim_high = await client.get("/api/v1/meters?limit=201")
        assert r_lim_high.status_code == 422
        assert r_lim_high.headers.get("content-type") == "application/problem+json"


@pytest.mark.asyncio
async def test_error_consistency_rfc7807_and_codes():
    """Tests consistent RFC 7807 problem details across 404, 405, and 422 error conditions."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unknown route (404)
        r_404 = await client.get("/api/v1/nonexistent/route")
        assert r_404.status_code == 404
        assert r_404.headers.get("content-type") == "application/problem+json"
        p_404 = r_404.json()
        assert p_404["code"] == "NOT_FOUND"
        assert p_404["status"] == 404

        # 2. Method not allowed (405)
        r_405 = await client.post("/api/v1/meters")
        assert r_405.status_code == 405
        assert r_405.headers.get("content-type") == "application/problem+json"
        p_405 = r_405.json()
        assert p_405["code"] == "METHOD_NOT_ALLOWED"
        assert p_405["status"] == 405

        # 3. Invalid date range from_date > to_date (422)
        r_date = await client.get("/api/v1/meters/J100000/consumption?from_date=2026-03-25&to_date=2026-03-10")
        assert r_date.status_code == 422
        assert r_date.headers.get("content-type") == "application/problem+json"
        p_date = r_date.json()
        assert p_date["code"] == "INVALID_DATE_RANGE"
        assert p_date["status"] == 422

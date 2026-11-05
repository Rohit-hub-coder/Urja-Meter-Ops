# Urja Meter Ops API Service

**Author**: Rohit Kumar  
**Roll No**: 23/SE/129  
**Institution**: Delhi Technological University (DTU)  
**Submission**: Take-Home Engineering Assignment for Flock Energy  
**Repository**: [https://github.com/Rohit-hub-coder/Urja-Meter-Ops.git](https://github.com/Rohit-hub-coder/Urja-Meter-Ops.git)

[![Python 3.11 | 3.12 | 3.14](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/tests-31%20passed-success.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-89%25-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-grade, resilient RESTful API and synchronization service built in front of the legacy **Urja Meter Ops** smart-metering web portal.

The service provides clean, normalized, and typed programmatic access to meter metadata, a 7-tier distribution network hierarchy, geospatial lookups, and 30-minute interval telemetry load curves without placing unnecessary load on the upstream portal.

---

## Reviewer Quick Tour (5 Minutes)

Run these six commands from the repository root to verify all core capabilities end-to-end:

```bash
# 1. Environment & Dependencies (Python 3.11 or 3.12 supported)
cp .env.example .env && make install

# 2. Run Complete Offline Test Suite (31 unit & integration tests, 89% coverage)
make test

# 3. Lint & Formatting Verification (zero warnings)
make lint

# 4. Start Local API Service (starts on port 8000, auto-syncs cache on boot)
make run &
sleep 3

# 5. Execute Verbatim Sample Request (Geospatial Radius Search)
curl -s "http://localhost:8000/api/v1/meters?near_lat=26.9124&near_lng=75.7873&radius_km=3.0&limit=1" | python3 -m json.tool

# 6. Check Operational Health & Upstream Reachability
curl -s "http://localhost:8000/api/v1/health" | python3 -m json.tool
```

---

## Deliverables & Document Index

As required by the **Flock Energy Engineering Take-Home** evaluation brief:

| Deliverable | Location | Description |
|---|---|---|
| **1. Source Code** | [`src/urja_api/`](src/urja_api/) | Complete FastAPI service, domain services, polite client, stateless parsers, SQLite repository, and zero-build web console. |
| **2. README** | [`README.md`](README.md) | The front door to the submission: architecture, installation, quick tour, sample requests, assumptions, trade-offs, omissions, and reflection. |
| **3. PROTOCOL.md** | [`PROTOCOL.md`](PROTOCOL.md) | Comprehensive write-up of the reverse-engineered portal: authentication/session lifecycle, SvelteKit CSRF, undocumented HMAC-SHA256 `/portal/export` bulk endpoint, telemetry cadence, and 403-meter census with quantified data quirks. |
| **4. openapi.json** | [`openapi.json`](openapi.json) | Complete OpenAPI 3.1 specification for the clean API service. Also served interactively via Swagger UI at `/docs` and ReDoc at `/redoc`. |
| **5. Notes** | Included below in README | Detailed coverage of [Assumptions & Design Decisions](#assumptions--design-decisions), [What Was Intentionally Left Out (and Why)](#what-was-intentionally-left-out-and-why), and [What We Would Improve With More Time](#what-we-would-improve-with-more-time). |
| **6. Reflection** | Included below & in [`REFLECTION.md`](REFLECTION.md) | Answers to the 5 mandatory evaluation questions: assumptions, hardest challenges, improvements with another day, mistakes made, and self-critique. |
| **Extra: Defense Notes** | [`DEFENSE_NOTES.md`](DEFENSE_NOTES.md) | Concrete interview defense answers, technical Q&A, and architectural deep dive. |

---

## Table of Contents
- [Reviewer Quick Tour (5 Minutes)](#reviewer-quick-tour-5-minutes)
- [Deliverables & Document Index](#deliverables--document-index)
- [Architecture Overview](#architecture-overview)
- [Project Directory Structure](#project-directory-structure)
- [Key Features & Optional Extensions Addressed](#key-features--optional-extensions-addressed)
- [Quickstart & Installation](#quickstart--installation)
- [Core API Reference](#core-api-reference)
- [Sample Requests & Responses](#sample-requests--responses)
- [Scope & Security](#scope--security)
- [Testing & Verification](#testing--verification)
- [Cache TTL Policy & Staleness Rules](#cache-ttl-policy--staleness-rules)
- [Assumptions & Design Decisions](#assumptions--design-decisions)
- [What Was Intentionally Left Out (and Why)](#what-was-intentionally-left-out-and-why)
- [What We Would Improve With More Time](#what-we-would-improve-with-more-time)
- [Engineering Reflection](#engineering-reflection)
- [AI-Use Disclosure](#ai-use-disclosure)

---

## Architecture Overview

```mermaid
flowchart TD
    Client(["Client / Front-End Consumer"]) -->|HTTP REST JSON| API["FastAPI Application (main.py)"]
    
    subgraph ServiceLayer ["Application & Service Layer"]
        API --> RouteMeters["GET /api/v1/meters"]
        API --> RouteConsumption["GET /api/v1/meters/{id}/consumption"]
        API --> RouteHierarchy["GET /api/v1/hierarchy"]
        API --> RouteSync["POST /api/v1/sync"]
        API --> RouteHealth["GET /api/v1/health"]
        
        RouteMeters --> MeterService["MeterService"]
        RouteConsumption --> EnergyService["EnergyService (15m Cache)"]
        RouteHierarchy --> HierarchyService["HierarchyService"]
        RouteSync --> SyncService["SyncService"]
    end
    
    subgraph StorageLayer ["Local Storage & Cache"]
        MeterService <--> SQLite[("SQLite Database (aiosqlite)\n• Bounding Box Prefilter\n• Indexed Attributes\n• SWR Metadata")]
        HierarchyService <--> SQLite
        SyncService -->|Batch Upsert| SQLite
    end

    subgraph ParserLayer ["Pure Stateless Parsers (Tested Offline)"]
        MeterParser["meter_parser.py"]
        HierarchyParser["hierarchy_parser.py (Auto-Repair)"]
        EnergyParser["energy_parser.py (IST, Deltas)"]
    end

    subgraph ClientLayer ["Polite Upstream Portal Client"]
        PortalClient["UrjaPortalClient\n• Semaphore(2) Max Concurrency\n• 200ms Rate Delay\n• Exponential Backoff & Jitter\n• RFC 7807 Error Mapping"]
        SessionMgr["SessionManager\n• Single-Flight Login (asyncio.Lock)\n• 1-Hour Cookie Management\n• HMAC-SHA256 Signer"]
        PortalClient <--> SessionMgr
    end

    SyncService --> PortalClient
    EnergyService --> PortalClient
    PortalClient --> ParserLayer
    PortalClient -->|HTTP/2 Read-Only| LegacyPortal[("Legacy Urja Meter Ops Portal\n(https://urja-ops.flockenergy.tech)")]
```

---

## Project Directory Structure

```
rohit-api/
├── .env.example               # Clean environment template (sanitized, zero secrets)
├── Makefile                   # Standardized automation: install, run, test, lint
├── openapi.json               # Full committed OpenAPI 3.1 schema specification
├── PROTOCOL.md                # Reverse-engineered wire protocol, CSRF, and quirks
├── README.md                  # Front door documentation & instructions
├── REFLECTION.md              # Engineering reflection & retrospective analysis
├── DEFENSE_NOTES.md           # Interview technical defense notes and architectural Q&A
├── WORKLOG.md                 # Chronological development log & verification record
├── pyproject.toml             # Python packaging, dependencies, and tool settings
├── src/
│   └── urja_api/
│       ├── main.py            # FastAPI entry point, lifespan, RFC 7807 handlers
│       ├── config.py          # Typed settings via pydantic-settings
│       ├── errors.py          # Domain exceptions & RFC 7807 ProblemDetails mapping
│       ├── api/               # API route definitions
│       │   └── routes/        # meters, consumption, hierarchy, sync, health
│       ├── client/            # Polite upstream HTTP client & session management
│       │   ├── portal_client.py   # Semaphore(2), 200ms pacing, jitter backoff
│       │   └── session_manager.py # Single-flight login lock, HMAC-SHA256 signer
│       ├── models/            # Pydantic v2 domain schemas (Meter, Hierarchy, Telemetry)
│       ├── parsers/           # Pure stateless parsers (tested offline against fixtures)
│       │   ├── meter_parser.py     # Meter record extraction & sanitization
│       │   ├── hierarchy_parser.py # Tree reconstruction & deterministic repair
│       │   └── energy_parser.py    # IST timezone parser, interval deltas, reset safety
│       ├── services/          # Business logic & query orchestration
│       ├── storage/           # SQLite persistence via aiosqlite & spatial bounding-box
│       └── web/               # Zero-build Web Operations Console (/ui)
├── tests/
│   ├── fixtures/              # Real anonymized wire fixtures captured from portal
│   ├── test_parsers.py        # Offline parser unit tests
│   ├── test_hierarchy.py      # Hierarchy tree rollup and repair tests
│   ├── test_api_mocked.py     # Mocked HTTP API integration tests (respx)
│   ├── test_openapi.py        # OpenAPI contract sync test
│   └── test_live_smoke.py     # Live portal smoke verification suite
├── docs/
│   ├── evidence/              # 14 captured evidence files from live portal exploration
│   └── examples/              # Sample JSON responses for radius queries and meter details
└── scripts/
    ├── telemetry_census.py    # Stratified 50-meter telemetry audit script
    ├── audit_hierarchy_integrity.py # Full 403-meter topology census script
    └── export_openapi.py      # OpenAPI JSON regeneration tool
```

---

## Key Features & Optional Extensions Addressed

Every core requirement and all six optional extensions from the evaluation brief are implemented:

1. **Network Hierarchy (Extension 1)**:
   - Full 7-tier topology reconstructed from the portal: `Zone` $\to$ `Circle` $\to$ `Division` $\to$ `Subdivision` $\to$ `Substation` $\to$ `Feeder` $\to$ `Distribution Transformer (DT)` $\to$ `Meter`.
   - Meter count rollups computed at every node level.
   - Dedicated `GET /api/v1/hierarchy` returns the complete tree; `GET /api/v1/hierarchy/nodes/{id}` provides targeted branch inspection with full ancestor paths.
   - **Automated Repair**: Transparently infers missing names/codes from peer nodes (affecting 22 meters, 5.46% of inventory) while explicitly surfacing `raw_code`, `raw_name`, and `DataQualityWarning` flags so raw upstream truth is never obscured.

2. **Local Index & Query Layer (Extension 2)**:
   - Indexed SQLite engine supporting multi-attribute filtering (`make`, `phase_type`, `install_status`, `dt_code`, `feeder_code`, and `q` substring text search).
   - **Two-Phase Geospatial Search**: Combines an indexed SQL bounding-box prefilter with exact in-memory Haversine distance calculations and sorting via `near_lat`, `near_lng`, and `radius_km`.
   - *Scale Analysis*: Sub-millisecond queries for the current regional inventory (403 meters); scales smoothly to ~50,000 meters. For larger utility footprints (>100k meters), the architecture cleanly migrates to SQLite's virtual R-Tree extension (`rtree`) or PostgreSQL/PostGIS.

3. **Freshness & Caching (Extension 3)**:
   - **Meter Metadata & Hierarchy**: 1-hour TTL with 24-hour Stale-While-Revalidate (SWR) window. Responses include `X-Cache: HIT|MISS|SWR` and `X-Data-Fetched-At` headers.
   - **Consumption Telemetry**: 15-minute TTL per `(meter_id, from, to)` window, reflecting the portal's 30-minute sampling cadence without query storms.
   - **Manual Sync Rate Limit**: 60-second cooldown on `POST /api/v1/sync` returning HTTP 429 with `Retry-After`.
   - Cache freshness, cache age in seconds, and staleness are continuously reported via `GET /api/v1/health`.

4. **Robustness & Polite Client (Extension 4)**:
   - Upstream connection pool capped at `PORTAL_MAX_CONCURRENCY=2` via `asyncio.Semaphore(2)`.
   - Sequential pacing delay of `PORTAL_REQUEST_DELAY_SEC=0.2s` (200ms) between page requests.
   - **Single-Flight Authentication**: Concurrent requests encountering an expired session wait on an `asyncio.Lock()` so only one login request reaches the upstream portal.
   - Exponential backoff with jitter on HTTP 429 and 5xx errors; automatic session renewal on HTTP 302 redirects.
   - Comprehensive RFC 7807 Problem Details mapping for all error conditions.

5. **Full Dataset Bulk Path (Extension 5)**:
   - Reverse-engineered first-party HMAC-SHA256 authenticated endpoint `/portal/export` discovered in Vite client chunk `4.2Bgc2kUI.js`.
   - Synchronizes all **403 meters** and **40 distribution transformers** in a single polite ~250ms request, bypassing 20+ sequential paged scrapes.
   - Automated secret invalidation retry on 401/403, with seamless fallback to paged `/portal/meters/search` crawling if export fails.

6. **Modern Web Client (Extension 6)**:
   - Zero-build Web Operations Console served at `http://localhost:8000/ui`.
   - Features vendored, offline-capable Leaflet mapping with marker clusters, Chart.js 30-minute interval load curves, interactive 7-tier network hierarchy tree explorer, live search/filtering, and meter detail inspector modals.

---

## Quickstart & Installation

### Prerequisites
- Python 3.11, 3.12, or 3.14 (fully verified across test suite)
- `uv` (recommended) or standard `python3 -m venv`

### 1. Clone & Configure
```bash
git clone https://github.com/Rohit-hub-coder/Urja-Meter-Ops.git urja-api
cd urja-api

# Create your local environment configuration
cp .env.example .env
```
Edit `.env` to include your portal credentials:
```ini
URJA_PORTAL_BASE_URL=https://urja-ops.flockenergy.tech
URJA_PORTAL_USERNAME=your_operator_email
URJA_PORTAL_PASSWORD=your_portal_password
PORT=8000
```

### 2. Install Dependencies
Using `uv`:
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e . -r <(echo -e "pytest>=9.0.0\npytest-asyncio>=1.4.0\nrespx>=0.23.0\nruff>=0.17.0")
```
Or using standard `pip`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e . pytest pytest-asyncio respx ruff
```

### 3. Run the Service
```bash
make run
# or directly:
uvicorn src.urja_api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Cold Start & Automatic Startup Synchronization
On initial boot (`make run`), the service inspects the local SQLite database. If the database is unseeded and portal credentials are provided in `.env`, the service initiates an initial bulk synchronization during startup lifespan, indexing all 403 meters and distribution transformers before serving traffic. If queries arrive before synchronization completes, endpoints like `/api/v1/meters` and `/api/v1/hierarchy` lazily trigger synchronization on first access.
`/api/v1/health` reports `status: "healthy"` once the index is populated. It reports `status: "degraded"` only when the upstream portal is temporarily unreachable (while cached data remains available for reads) or when cache staleness exceeds configured TTLs.

The service is now running at `http://localhost:8000`:
- **Interactive OpenAPI Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **ReDoc API Spec**: `http://localhost:8000/redoc`
- **Zero-Build Web Console**: `http://localhost:8000/ui`
- **Health & Readiness Check**: `http://localhost:8000/api/v1/health`

---

## Core API Reference

| Endpoint | Method | Description | Cache / Headers |
|---|---|---|---|
| `/api/v1/meters` | `GET` | List/filter meters (make, phase, status, DT, spatial radius `near_lat`/`near_lng`/`radius_km`). | `X-Cache: HIT/MISS`, `X-Data-Fetched-At` |
| `/api/v1/meters/{id}` | `GET` | Retrieve complete meter details, nameplate attributes, and hierarchy links. | `X-Cache: HIT/MISS` |
| `/api/v1/meters/{id}/consumption` | `GET` | 30-minute interval telemetry series, cumulative registers, and window summary. | `X-Cache: SWR` (15m TTL) |
| `/api/v1/hierarchy` | `GET` | Full 7-tier network tree with rolled up meter counts at every node. | `X-Cache: HIT` (1h TTL) |
| `/api/v1/hierarchy/nodes/{id}` | `GET` | Node detail view with full ancestor path and immediate children. | `X-Cache: HIT` |
| `/api/v1/sync` | `POST` | Trigger bulk synchronization into SQLite index (cooldown rate-limited). | -- |
| `/api/v1/health` | `GET` | Service operational health, upstream reachability, latency, and cache age. | -- |

---

## Sample Requests & Responses

### 1. Geospatial Radius Search (List View)
`GET /api/v1/meters?near_lat=26.9124&near_lng=75.7873&radius_km=3.0&limit=1`

Returns matching meters ordered by distance, including complete 7-tier hierarchy and pagination metadata:
```json
{
  "data": [
    {
      "meter_id": "J100368",
      "serial_number": "L&37528",
      "make": "HPL",
      "phase_type": "three",
      "install_status": "Faulty",
      "install_type": "Whole Current",
      "build_version": "legacy",
      "dt_code": "DT-009",
      "location": { "latitude": 26.916888, "longitude": 75.784779, "distance_km": 0.558 },
      "hierarchy": {
        "zone": { "code": "Z-03", "name": "Jaipur Zone 3", "raw_code": "Z-03", "raw_name": "Jaipur Zone 3", "is_inferred": false },
        "circle": { "code": "C-03", "name": "Circle 3", "raw_code": "C-03", "raw_name": "Circle 3", "is_inferred": false },
        "division": { "code": "D-09", "name": "Division 9", "raw_code": "D-09", "raw_name": "Division 9", "is_inferred": false },
        "subdivision": { "code": "SD-09", "name": "Subdivision 9", "raw_code": "SD-09", "raw_name": "Subdivision 9", "is_inferred": false },
        "substation": { "code": "SS-09", "name": "Substation 9", "raw_code": "SS-09", "raw_name": "Substation 9", "is_inferred": false },
        "feeder": { "code": "F-009", "name": "Feeder 9", "raw_code": "F-009", "raw_name": "Feeder 9", "is_inferred": false },
        "dt": { "code": "DT-009", "name": "Sikar Road DT 9", "raw_code": "DT-009", "raw_name": "Sikar Road DT 9", "is_inferred": false }
      },
      "data_quality_warnings": []
    }
  ],
  "pagination": { "total_records": 16, "page": 1, "limit": 1, "total_pages": 16, "has_next": true, "has_prev": false },
  "data_quality_warnings": []
}
```
*See full formatted response:* [docs/examples/meter_search_radius_sample.json](docs/examples/meter_search_radius_sample.json)

### 2. Meter Detail View
`GET /api/v1/meters/J100368`

Returns full meter record with extended nameplate attributes and complete network path:
*See full response:* [docs/examples/meter_detail_sample.json](docs/examples/meter_detail_sample.json)

### 3. RFC 7807 Problem Details Error
`GET /api/v1/meters/UNKNOWN_METER`

```json
{
  "type": "https://api.urja-ops.local/errors/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Meter 'UNKNOWN_METER' was not found.",
  "instance": "/api/v1/meters/UNKNOWN_METER",
  "code": "NOT_FOUND"
}
```

### 4. Telemetry Load Curve / Consumption
`GET /api/v1/meters/J100000/consumption?from_date=2026-06-24&to_date=2026-06-25`

Returns 30-minute interval consumption series with calculated interval deltas ($\Delta\text{kWh}$), voltage, and aggregate summary:
```json
{
  "meter_id": "J100000",
  "granularity": "30-minute",
  "readings": [
    {
      "timestamp_iso": "2026-06-24T00:00:00+05:30",
      "cumulative_active_energy_kwh": 48439.16,
      "cumulative_apparent_energy_kvah": 52314.29,
      "interval_active_energy_kwh": null,
      "voltage_phase_r_volts": 229
    },
    {
      "timestamp_iso": "2026-06-24T00:30:00+05:30",
      "cumulative_active_energy_kwh": 48439.88,
      "cumulative_apparent_energy_kvah": 52315.02,
      "interval_active_energy_kwh": 0.72,
      "voltage_phase_r_volts": 230
    }
  ],
  "summary": {
    "start_time": "2026-06-24T00:00:00+05:30",
    "end_time": "2026-06-24T23:30:00+05:30",
    "total_readings": 48,
    "total_active_energy_consumed_kwh": 34.52,
    "average_voltage_volts": 231.4,
    "min_voltage_volts": 226,
    "max_voltage_volts": 238
  },
  "data_quality_warnings": []
}
```

---

## Scope & Security

1. **Strictly Read-Only Operational Boundary**:
   - The API is an unprivileged consumer of the upstream portal. It makes only idempotent HTTP `GET` queries (and `POST /login` for authentication).
   - Never touches or exposes administrative, write, update, or delete capabilities.
2. **Polite Client Enforcement**:
   - Upstream connection pool capped at `PORTAL_MAX_CONCURRENCY=2` via `asyncio.Semaphore(2)`.
   - Sequential pacing delay of `PORTAL_REQUEST_DELAY_SEC=0.2s` (200ms) between page crawls.
   - Upstream timeout set to 15.0 seconds with exponential backoff and jitter on HTTP 429/5xx.
3. **Secret & Key Handling**:
   - Operator credentials exist only in git-ignored `.env`. Never logged, committed, or exposed.
   - HMAC signing secret dynamically fetched into volatile process memory; auto-invalidated on 401/403.
   - No signing secrets, session tokens, or passwords exist in git history, docs, or fixtures.
4. **Error Sanitization & Information Masking**:
   - RFC 7807 `application/problem+json` format for all client and server errors.
   - Stack traces and internal Python exceptions are strictly suppressed.
5. **Privacy & Data Protection (PII Audit)**:
   - Portal dataset audited: contains 0 customer names, 0 phone numbers, 0 billing accounts, and 0 personal identifiers. Data consists exclusively of grid operational assets and geo-coordinates.

---

## Testing & Verification

The test suite covers offline parser verification, upstream failure mocking, spatial queries, and live end-to-end smoke verification:

```bash
# Run complete offline test suite (31 unit & integration tests)
make test

# Run test suite with statement coverage (89% total coverage)
pytest --cov=src --cov-report=term-missing tests/

# Run code style and formatting checks
make lint

# Run live smoke test against live portal (verifies real portal output)
make test-live
```

### Test Suite Structure
- `tests/test_parsers.py`: Unit tests verifying pure parser functions against captured real fixtures (`tests/fixtures/`).
- `tests/test_hierarchy.py`: Tests tree reconstruction, meter count rollups, and intentional handling of messy hierarchy data.
- `tests/test_api_mocked.py`: Comprehensive API tests with mocked portal upstream (`respx`):
  - Session expiration & single-flight re-login.
  - Upstream 502/504 error mapping.
  - Export secret invalidation on 403 and fallback crawl.
  - Startup auto-sync via lifespan on cold boot.
  - Manual sync cooldown rate limit (429 with `Retry-After`).
  - Spatial radius search and sorting.
  - Pagination bounds validation (out-of-bounds page/limit -> 422).
  - Web Console `/ui` and vendored static assets serving.
- `tests/test_openapi.py`: Ensures committed `openapi.json` is never stale or out of sync with the codebase.
- `tests/test_live_smoke.py`: Live read-only smoke test against the actual portal (guarded by `ENABLE_LIVE_PORTAL_TESTS=true`).

---

## Cache TTL Policy & Staleness Rules

> **Empirical Context**: During reverse-engineering investigation, the upstream portal data remained static (`total: 403` meters, telemetry fixed up to 30/06/2026) **[OBSERVED]**. TTL configurations reflect realistic operational utility parameters:

| Resource Type | Cache Location | Default TTL | Staleness / SWR Policy | Justification & Observed vs Assumed Context |
|---|---|---|---|---|
| **Meter Metadata & Hierarchy** | SQLite Index | **1 Hour** (3,600s) | Stale-While-Revalidate up to 24 hours (`X-Cache: HIT`, `X-Data-Fetched-At`) | Structural distribution network master data (zones, substations, feeders, transformers) changes infrequently in power utilities **[ASSUMED]**. |
| **Consumption Telemetry** | In-Memory TTL Cache | **15 Minutes** (900s) | Re-fetched on expiry; cached per `(meter_id, from, to)` window | Telemetry is sampled at 30-minute block intervals for active meters **[OBSERVED]**. A 15-minute TTL guarantees fresh readings at half the collection cadence without query storms **[ASSUMED]**. |
| **Manual Sync Route** | `POST /api/v1/sync` | Cooldown: **60 Seconds** | Returns HTTP 429 if triggered within cooldown period | Protects upstream `/portal/export` from flooding or denial-of-service from repeated client sync requests **[OBSERVED polite client requirement]**. |
| **Portal Session Token** | Memory (`SessionManager`) | **50 Minutes** (buffer before 60m expiry) | Single-flight re-login on 302 redirect or token expiry | Upstream cookie `__Secure-better-auth.session_token` has `Max-Age=3600` **[OBSERVED]**. A 50-minute renewal prevents mid-flight session expiration. |

---

## Assumptions & Design Decisions

| Category | Decision / Assumption | Justification |
|---|---|---|
| **Bulk Path** | Use HMAC-signed `/portal/export` endpoint discovered in client chunks | Synchronizes all 403 meters in 1 request (~250ms) vs. 21+ sequential paged scrapes. |
| **Export Resilience** | Secret invalidation retry + automatic fallback to paged search crawl | If `/portal/export` returns 401/403, the client invalidates the cached secret and retries once; if persistent failure occurs, it falls back to paginating `/portal/meters/search`. The fallback captures 100% of meters (403/403) and master fields, but has partial hierarchy (DT only) and lacks geo-coordinates without individual lookups. See [PROTOCOL.md §3.1.2](PROTOCOL.md). |
| **Hierarchy Tiers** | Full 7-tier topology on both list and detail views | Both `MeterSummary` (list) and `MeterDetail` (detail) expose all 7 tiers (`zone`, `circle`, `division`, `subdivision`, `substation`, `feeder`, `dt`). This prevents N+1 queries by allowing API consumers to group, aggregate, or slice search results by substation or feeder without needing individual detail calls. The detail view additionally returns extended `nameplate_attributes`. |
| **Data Repair** | Inferred missing hierarchy codes/names from peer nodes with `data_quality_warnings` | Prevents broken tree visualization while preserving full auditability of upstream anomalies. |
| **Storage** | SQLite (`aiosqlite`) with bounding-box prefilter | Embedded, zero external dependencies, sub-millisecond query latency for regional utility datasets. |
| **Concurrency** | Polite client bounded to 2 concurrent in-flight requests | Prevents denial of service or disruption on legacy utility portal. |
| **Timezone** | All timestamps normalized to IST (UTC+05:30) | Utility is located in Jaipur, Rajasthan. Standardizes telemetry across consumers. |

---

## What Was Intentionally Left Out (and Why)

As required by Deliverable 5 of the evaluation brief:

1. **Write / Mutating Operations**: Intentionally omitted. The brief explicitly instructs to treat the legacy portal as read-only. No meter provisioning, topology modification, or telemetry override endpoints exist in scope.
2. **External Infrastructure Daemons (PostgreSQL, Redis, RabbitMQ)**: Intentionally skipped running external service containers in favor of embedded SQLite (`aiosqlite`) and in-process mutexes/caches. This guarantees that the entire submission installs, builds, and passes tests locally with zero background setup or Docker requirements.
3. **Eager Geo-Scrapes during Paged Crawl Fallback**: In the emergency fallback path when `/portal/export` is unreachable, the synchronization engine paginates `/portal/meters/search` and maps distribution transformers from `/portal/dts`. This reliably discovers 100% of meters (403/403), but coordinates are left `null` rather than firing 403 sequential `/portal/meters/{id}/geo` requests, which would violate polite client latency constraints.
4. **Parameterized Downsampling Query Options**: The consumption endpoint currently exposes native 30-minute block interval series. Real-time parameterized downsampling (`granularity=hourly|daily`) was omitted to prioritize accurate counter-reset handling and interval delta computation.
5. **Node.js Build Pipeline for the Web UI**: The Web Operations Console served at `/ui` is zero-build vanilla HTML, CSS, and JavaScript. Assets (Leaflet, Chart.js) are vendored locally so reviewers do not need `npm` or `node`.

---

## What We Would Improve With More Time

1. **Streaming JSON Ingestion (`ijson`)**:
   - Currently, the 403-meter JSON bulk export is parsed into memory in ~15ms. To scale to 1,000,000 meters, we would stream and batch records in 500-meter chunks using `ijson` to bound memory footprint at $O(1)$.
2. **Distributed Redis Coordination for Multi-Worker Deployments**:
   - The current single-flight mutex lock in `SessionManager` uses in-process `asyncio.Lock()`. For multi-worker deployments (`uvicorn --workers 4`) or Kubernetes horizontal pod autoscaling, we would migrate session synchronization and telemetry caching to Redis using Redlock.
3. **SQLite R-Tree Spatial Indexing**:
   - For higher spatial density (tens of thousands of meters), we would migrate the 2D bounding-box prefilter to an SQLite virtual table with the `rtree` extension or PostgreSQL PostGIS for native spatial indexing.
4. **Server-Side Downsampling Aggregations**:
   - Add query parameter `granularity=raw|hourly|daily|monthly` to aggregate 30-minute load curves into daily averages directly inside the database query engine.
5. **Proactive Background Crawler**:
   - Introduce an asynchronous scheduler (e.g. APScheduler) to proactively re-sync the meter index during off-peak hours rather than relying on lazy request-time revalidation.

---

## Engineering Reflection

Below is the concise candidate reflection answering the five mandatory evaluation questions (a paragraph each). For extended analysis, see [`REFLECTION.md`](REFLECTION.md).

### 1. What assumptions did you make?
I assumed that portal timestamps (`DD/MM/YYYY HH:MM`) represent Indian Standard Time (IST, UTC+05:30), reflecting Jaipur, Rajasthan's distribution grid, and normalized them to ISO-8601 with explicit offsets. I recognized that cumulative telemetry registers (`kwh`, `kvah`) are monotonically increasing counter registers from meter nameplates, and derived interval consumption as $\Delta\text{kWh} = \text{kWh}_i - \text{kWh}_{i-1}$, handling regressions by setting interval delta to `null` with a `DataQualityWarning`. I also assumed that utility topology changes infrequently, justifying a 1-hour cache TTL with 24-hour Stale-While-Revalidate in local SQLite, and that polite client limits (concurrency 2, 200ms delays, single-flight re-login locks) are required to protect legacy utility infrastructure.

### 2. Which part was the most difficult, and how did you get unstuck?
The two hardest challenges were SvelteKit's CSRF rejection on programmatic login and reverse-engineering the bulk export endpoint. Initial `POST /login` attempts failed with HTTP 403 (`Cross-site POST form submissions are forbidden`). Inspecting browser devtools traffic revealed SvelteKit validates the `Origin` header against the request host; supplying explicit `Origin` and `Referer` headers resolved authentication immediately. Later, analyzing client Vite chunk `4.2Bgc2kUI.js` revealed the HMAC-SHA256 authenticated `/portal/export` route. Reconstructing the canonical string (`GET\n/portal/export\npage=1\n<timestamp>`), dynamically fetching the secret from `/portal/keys`, and implementing automatic secret retry and paged search fallback unlocked instantaneous 403-meter synchronization.

### 3. If you had another day, what would you improve?
With another day, I would implement streaming JSON ingestion (`ijson`) to keep memory footprint $O(1)$ when synchronizing millions of meters, and migrate in-process `asyncio.Lock()` mutexes to Redis Redlock to enable multi-worker (`uvicorn --workers 4`) and horizontal pod autoscaling. I would also add native SQLite R-Tree spatial indexing for high-density spatial queries and expose server-side downsampling query parameters (`granularity=hourly|daily`) on the telemetry load curve endpoint.

### 4. What mistake did you make while solving this?
Early in development, I made four concrete mistakes: (1) included the portal domain in `.env.example` User-Agent placeholder, which was caught by pre-commit secret scans and sanitized to the public GitHub repository identifier; (2) assumed meter serial numbers always start with `"SE"` based on `J100000`, causing tests to fail on Genus meter `J100001` (`GE84132`); (3) caught a generic `Exception` on cold-start cache misses and masked upstream 502/503 errors as 404 Not Found, which I refactored to cleanly propagate RFC 7807 503 ProblemDetails; and (4) hypothesized daily-cadence meters were older hardware, which empirical census disproved (finding an exact 50/50 split across `v2` and `legacy` builds), prompting me to retract the unverified claim from documentation.

### 5. If you were reviewing your own submission, what would you criticise?
I would criticise the single-worker in-memory concurrency model: because `SessionManager` uses an in-process `asyncio.Lock()`, running multiple Uvicorn workers results in separate session pools and redundant upstream logins. I would also criticise upstream telemetry filtering waste: because the portal's `/portal/meters/{id}/energy` endpoint ignores sub-day timestamps, querying a 2-hour window still pulls an entire day of records and filters them in Python. Finally, telemetry downsampling is not yet parameterized via API query parameter.

---

## AI-Use Disclosure

In accordance with the take-home evaluation ground rules:
- **Guidance & Tips Only**: AI assistance was used strictly for high-level guidance, conceptual tips, and syntax/error unblocking (such as understanding SvelteKit form action CSRF checks).
- **Independent Execution**: All core investigation, reverse-engineering of the legacy portal wire protocols, architectural design, code implementation, test suites, and documentation were performed directly by me.
- **Empirical Verification**: Every single portal wire format, endpoint behavior, hierarchy quirk, and edge case was empirically probed directly against the live portal, captured into `docs/evidence/`, saved as offline fixtures in `tests/fixtures/`, and verified with passing automated test suites.

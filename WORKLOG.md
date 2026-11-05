# Engineering Worklog: Urja Meter Ops API Service
**Author**: Rohit Kumar (Roll No: 23/SE/129, Delhi Technological University)

This worklog records raw, chronological engineering decisions, hypotheses, investigation findings, mistakes, dead ends, and verified facts throughout the project.

---

### [2026-11-05 10:41] Phase 0: Initial Scoping & Plan Approval
- **Decision**: Prioritize Phase 1 investigation (60-75 min) over speculative architecture. Clean reverse-engineering of the legacy portal is the single point of failure for downstream parsers and API contracts.
- **Decision**: Git repository initialized with strict `.gitignore` enforcing secret isolation (`.env`, `DEFENSE_NOTES.md`, `*.db`). `.env.example` created with sanitized placeholders.
- **Hypothesis**: The legacy portal "Urja Meter Ops" is likely a traditional server-rendered application (Flask/Django/PHP/ASP.NET or legacy React/Vue monolith). It might possess hidden export routes (CSV/JSON/XLSX), internal query parameters, or undocumented API paths.
- **Rule of Engagement**: Read-only operations exclusively. Maximum 2 concurrent requests, respectful delays (300ms), descriptive User-Agent, bounded timeouts, and redaction of all session tokens in captured evidence.

---

### [2026-11-05 10:45] Phase 1: Authentication & Framework Discovery
- **Action**: Probed `GET /robots.txt`, `GET /sitemap.xml`, `GET /login`.
- **Finding (OBSERVED)**: `robots.txt` returned 200 with `Disallow: `. `sitemap.xml` returned 404 with SvelteKit fallback.
- **Finding (OBSERVED)**: Portal is built on **SvelteKit** with frontend client hydration bundles (`/_app/immutable/...`).
- **Trap / Mistake Identified**: Initial `POST /login` returned HTTP 403 `Cross-site POST form submissions are forbidden`.
  - *Root cause*: SvelteKit enforces CSRF check by verifying `Origin` and `Referer` headers on all POST form submissions.
  - *Correction*: Added `Origin: https://urja-ops.flockenergy.tech` and `Referer: https://urja-ops.flockenergy.tech/login` to upstream client headers.
- **Finding (OBSERVED)**: Valid login sets cookie `__Secure-better-auth.session_token` with `Max-Age=3600` (1 hour lifetime), `HttpOnly; Secure; SameSite=Lax`.
- **Finding (OBSERVED)**:
  - If `Accept: application/json` is sent, SvelteKit returns HTTP 200 with JSON `{"type":"redirect","status":303,"location":"/meters"}`.
  - If `Accept: text/html` is sent, it returns HTTP 303 redirect with `Location: /meters`.
  - On bad credentials, returns HTTP 200 with JSON payload containing `status: 401, data: ... "Invalid email or password."`.
  - On unauthenticated or expired session access to protected pages, the portal returns HTTP 302 redirecting to `/login` (silent redirect).

---

### [2026-11-05 10:47] Phase 1: Client Bundle Reverse Engineering & Undocumented Endpoints
- **Action**: Inspected Vite client chunks: `app.03ZTmlg3.js`, `4.2Bgc2kUI.js` (Transformers), `5.C4dYcCRt.js` (Meters), and `6.l777LXKL.js` (Meter Detail).
- **Major Breakthrough (OBSERVED)**:
  1. `/portal/meters/search?q={query}&page={page}`: Paged meter search (fixed limit: 20/page). Only searches `meterId` or `serialNo`.
  2. `/portal/dts?page={page}`: Paged distribution transformers (20/page, 40 total DTs).
  3. `/portal/keys`: Returns `{ "data": { "signingSecret": "..." } }`.
  4. `/portal/export?page=1`: **HMAC-SHA256 authenticated bulk export endpoint!**
     - Requires headers: `x-timestamp` (unix epoch) and `x-signature` (HMAC-SHA256 hex digest).
     - String to sign: `GET\n/portal/export\npage=1\n<timestamp>`.
     - Signing key: `signingSecret` obtained from `/portal/keys`.
     - Returns all **403 meters in a single JSON payload** including complete network hierarchy and coordinates.
     - Paging parameter is a dummy: `page=1` and `page=2` both return the entire 403-record dataset.
  5. `/portal/meters/{meterId}/geo`: Returns `{ "data": { "latitude": "...", "longitude": "..." } }`.
  6. `/portal/meters/{meterId}/energy`: Returns 337 half-hourly load survey readings.
  7. `/meters/{meterId}/__data.json`: SvelteKit SSR data containing nameplate detail attributes.
  8. `/api/auth/sign-out`: Session termination.

---

### [2026-11-05 10:49] Phase 1: Data Model, Spatial & Quirks Census (403 Meters)
- **Dataset Size (OBSERVED)**: Exactly 403 meters, 40 Distribution Transformers.
- **Attributes Breakdown**:
  - Unique Meter IDs: 403/403 (Zero duplicates, prefixed e.g. `J100000` to `J100402`).
  - Unique Serial Numbers: 403/403 (Zero duplicates, e.g. `SE33962`).
  - Makes: HPL (90), Genus (88), Secure (85), Allied (76), L&T (64).
  - Phases: `single` (277), `three` (126).
  - Statuses: `Installed` (238), `Faulty` (90), `Decommissioned` (75).
  - Install Types: `Whole Current` (205), `CT Operated` (198).
  - Builds: `legacy` (238), `v2` (165).
- **Spatial Cleanliness (OBSERVED)**:
  - 403 / 403 meters have coordinates (0 nulls, 0 missing).
  - 0 swapped lat/lng detected.
  - 0 out-of-range coordinates.
  - All coordinates cluster strictly in Jaipur, Rajasthan: Latitude `26.7881` to `27.0369`, Longitude `75.6625` to `75.9122`.
  - Type quirk: `/portal/meters/{id}/geo` returns coordinates as strings, while `/portal/export` returns floats.
- **Hierarchy Structure & Anomalies (OBSERVED)**:
  - Complete 7-tier topology: Zone (3) -> Circle (6) -> Division (10) -> Subdivision (13) -> Substation (18) -> Feeder (28) -> DT (40) -> Meters (403).
  - Exactly 22 meters (5.46%) contain asymmetric blank fields in hierarchy:
    - 6 meters have Circle name (e.g. "Circle 6") but `code: ""`.
    - 5 meters have Circle code (e.g. "C-01") but `name: ""`.
    - 5 meters have Feeder name (e.g. "Feeder 5") but `code: ""`.
    - 3 meters have Feeder code (e.g. "F-003") but `name: ""`.
    - 3 meters have Substation name (e.g. "Substation 16") but `code: ""`.
    - 0 meters have both name and code missing.
    - Zero orphaned meters (all 403 reference a valid DT in `/portal/dts`).
    - Zero multi-parent DT conflicts.
- **Energy / Consumption Quirks (OBSERVED)**:
  - Timestamp format: `DD/MM/YYYY HH:MM` (Indian standard format, local IST).
  - Granularity: Exactly 30-minute intervals (half-hourly load survey).
  - Readings window: 7-day snapshot (2026-06-23 23:30 to 2026-06-30 23:30), total 337 data points.
  - Units & Semantics: `kwh` and `kvah` are cumulative register counters (monotonically increasing float strings), NOT interval delta energy. `voltR` is voltage in Volts on Phase R.
  - Parameter filtering: Native `from=YYYY-MM-DD` and `to=YYYY-MM-DD` query parameters are supported upstream. Granular ISO time strings are ignored by upstream.

---

### [2026-11-05 10:52] Phase 1: Cache TTL & Upstream Policy Formulation
- **Session Policy**:
  - `better-auth` session token has `Max-Age=3600` (60 minutes).
  - Portal client will cache session token with 50-minute safety refresh window, and implement single-flight re-login on HTTP 302 / redirect detection.
- **Data Freshness Policy**:
  - **Meters Master & Hierarchy**: Static utility topological data. TTL = **1 hour**, Stale-While-Revalidate (SWR) window = 24 hours.
  - **Energy / Consumption**: Half-hourly telemetry data. TTL = **15 minutes** (half the 30-minute sampling interval).
  - **Manual Refresh**: `POST /api/v1/refresh` with a 60-second cooldown rate limit to prevent upstream flooding.

---

## 2026-11-05 12:15 - Final Verification Pass & Stratified Telemetry Census
- **Hypothesis**: Active meters have 30-minute cadences, while meters with 8 daily records represent older legacy billing meters.
- **Empirical Execution**: Ran rate-limited audit across 50 stratified meters (`scripts/telemetry_census.py`, concurrency 2, delay 250ms) spanning all 30 (make × phase × status) strata.
- **Findings**:
  - Exactly 32 meters had 30-min cadence (337 readings), 18 meters had daily midnight snapshot cadence (8 readings).
  - 0 negative counter regressions, 0 timestamp gaps, 0 duplicate timestamps.
  - 100% of decommissioned meters retain historical telemetry.
- **Mistake & Course Correction**:
  - We hypothesized daily cadence correlated with older firmware or "legacy billing meters". When checking the 18 daily meters against the database, exactly 9 were `build_version: "v2"` and 9 were `build_version: "legacy"`.
  - The hypothesis was **not supported by data**. Reworded `PROTOCOL.md` and census docs to label this hypothesis as unverified / refuted by data.

---

## 2026-11-05 12:35 - Upstream Failure Handling & Export Resilience Failover
- **Problem**: When the portal is unreachable and the local cache is empty, querying `GET /api/v1/meters/{id}` caught a generic `Exception` and converted it to `NotFoundError` (404), incorrectly telling the client the meter didn't exist instead of reporting upstream unavailability.
- **Fix**: Caught `(UpstreamUnavailableError, UpstreamTimeoutError)` explicitly in `MeterService.get_meter` and re-raised them so RFC 7807 503 is returned. Verified with live test.
- **Export Resilience**: Added automatic signing secret invalidation retry on 401/403 in `UrjaPortalClient.fetch_meters_bulk`. If persistent failure occurs, `SyncService` falls back to paginating `/portal/meters/search` and merging with `/portal/dts`. Added respx tests covering both failover paths.
- **Hierarchy Representation**: Confirmed and documented that both list and detail views provide all 7 network topology tiers (`zone` through `dt`) to allow consumer-side grouping without N+1 requests. Detail view adds `nameplate_attributes`.

## Phase 5: Final Verification & Polish (Complete)
- **Counter-Reset Handling**: Aligned code, tests, and documentation to set `interval_active_energy_kwh = None` with a structured `DataQualityWarning` on negative counter regressions.
- **Doc-vs-Code Audit**: Audited 18 concrete claims across README, PROTOCOL, and DEFENSE_NOTES. Corrected rate delay discrepancy from 300ms to 200ms (`0.2s`), perfectly matching `src/urja_api/config.py:22` and `portal_client.py:56`.
- **User-Agent Standard**: Standardized default User-Agent across `config.py`, `.env.example`, and `.env` to `UrjaMeterOpsApi/1.0 (take-home candidate; https://github.com/<GITHUB_USERNAME>/<REPO_NAME>)`.
- **AI Disclosure & Reflection**: Authored first-person engineering reflection in `REFLECTION.md` detailing tool use (Antigravity with `<MODEL NAME>` + Claude in separate unlinked chat), human decisions, verified mistakes, and `[USER TO CONFIRM]` markers.
- **Web UI Offline Vendoring**: Vendored Leaflet (JS, CSS, images) and Chart.js locally into `src/urja_api/web/static/vendor/` and mounted `/static`. Documented that map background tiles require internet while UI logic and charts run offline.
- **Multi-Python Verification**: Verified full test suite execution on Python 3.11 (`cpython-3.11.16`) and Python 3.12 (`cpython-3.12.14`) via `uv`.
- **Fresh Clone Resilience**: Tested application startup and endpoint querying without `.env` or SQLite database. Verified clean RFC 7807 ProblemDetails responses without stack traces.
- **Hierarchy Integrity Audit**: Built and executed automated census (`scripts/audit_hierarchy_integrity.py`), generating `docs/evidence/14_hierarchy_integrity.md`. Discovered dual naming on `DT-007` (`Sanganer DT 7` vs `Old Malviya Nagar Xfmr` on meters `J100400`-`J100402`).
- **Error Consistency & OpenAPI**: Registered `StarletteHTTPException` handler in `main.py` ensuring 404 and 405 return `application/problem+json`. Attached `ProblemDetails` schema to OpenAPI routes and regenerated `openapi.json`.
- **Test Suite Expansion**: Added unit tests for startup sync lifespan, 429 sync cooldown with `Retry-After`, `/ui` static assets, pagination boundary validation, and error consistency. Test suite now contains 31 passing offline tests with 89% statement coverage.
- **PII & Privacy Audit**: Audited documentation and fixtures; verified zero customer names, zero phone numbers, and zero personal credentials exposed in repo. Documented findings in `PROTOCOL.md §6`.
- **CI Workflow**: Added `.github/workflows/ci.yml` (25 lines) testing Python 3.11 and 3.12 matrices with lint, format, and coverage checks without requiring repository secrets.

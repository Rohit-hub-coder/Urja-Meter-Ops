# Urja Meter Ops API: System Defense & Architectural Walkthrough
**Author**: Rohit Kumar (Roll No: 23/SE/129, Delhi Technological University)

---

## 1. High-Level Architecture & Layering

```
                            [ Client / Consumer / Web UI ]
                                          │
                                   HTTP / REST JSON
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Application (main.py)                                                  │
│   ├── RFC 7807 Exception Handlers (ProblemDetails)                              │
│   └── Route Handlers (/meters, /consumption, /hierarchy, /sync, /health)        │
└─────────────────────────────────────────┬───────────────────────────────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
┌──────────────────────────────────────┐     ┌────────────────────────────────────┐
│ Services & Domain Layer             │     │ Local Storage & Cache (SQLite)     │
│   ├── MeterService                   │◄───►│   ├── meters (indexed attributes)   │
│   ├── EnergyService (15m TTL cache)  │     │   ├── transformers (DTs)           │
│   ├── HierarchyService (tree rollup) │     │   └── cache_metadata (SWR tracking)│
│   └── SyncService (idempotent bulk)  │     └────────────────────────────────────┘
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Pure Parsers Layer                   │
│   ├── meter_parser                   │  (Tested offline 100% against real fixtures)
│   ├── hierarchy_parser (data repair) │
│   └── energy_parser (IST, deltas)    │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Polite Portal Client Layer (client/)                                           │
│   ├── SessionManager: Single-flight re-login (asyncio.Lock), 1-hr cookie        │
│   ├── Rate Controls: Semaphore(2) concurrency, 200ms delays, bounded backoff    │
│   └── HMAC-SHA256 Signer: dynamic secret from /portal/keys for /portal/export   │
└─────────────────────────────────────────┬───────────────────────────────────────┘
                                          │
                               HTTP/2 (Read-Only)
                                          ▼
                      [ Legacy Urja Meter Ops Portal ]
```

---

## 2. Evidence Behind Every Assumption (Quantified Census)

* **Meter Census**: Exactly 403 meters (`J100000` to `J100402`), 0 duplicate IDs, 0 duplicate serial numbers.
* **Distribution Transformers**: Exactly 40 DTs (`DT-001` to `DT-040`), 0 orphaned meters, 0 multiple parent DT conflicts.
* **Geospatial Integrity**: 403 / 403 valid coordinates within Jaipur metropolitan bounds (Lat 26.7881–27.0369, Lng 75.6625–75.9122). Zero null coordinates, zero swapped coordinates.
* **Hierarchy Anomalies**: Exactly 22 meters (5.46%) had asymmetric partial entries (6 circle missing code, 5 circle missing name, 5 feeder missing code, 3 feeder missing name, 3 substation missing code). Zero missing both.
* **Telemetry Cadence**: In a 50-meter stratified sample, 32 meters report 30-min interval data (337 records), 18 meters report daily midnight snapshots (8 records). Zero counter regressions, zero timestamp gaps, zero duplicates. 100% of decommissioned meters retain historical readings.

---

## 3. Architecture & System Defense: Deep-Dive Technical Questions & Answers

### Q1: Why is using `/portal/export` NOT an access-control bypass or exploit?
**Answer**:
"Because `/portal/export` is a first-party, standard read-only client capability built into the portal by its own developers. In the client SvelteKit bundle (`/_app/immutable/nodes/4.2Bgc2kUI.js`), the 'Export all meters' button on `/transformers` directly executes this call. Both `/portal/keys` and `/portal/export` run strictly within the standard operator user session cookie (`__Secure-better-auth.session_token`).
No elevated privileges, no hidden administration tokens, no SQL injection, and no security boundaries were bypassed. We merely invoke the identical read-only endpoint that the web portal's own frontend calls, but do so with polite rate limits, bounded concurrency (max 2), and structured caching."

### Q2: How exactly is the HMAC signature constructed and verified?
**Answer**:
"The portal requires two HTTP headers: `x-timestamp` and `x-signature`.
1. The client retrieves the current signing secret dynamically from `GET /portal/keys` (e.g. `{"data": {"signingSecret": "..."}}`).
2. The signing payload is constructed as a newline-delimited canonical string:
   `GET\n/portal/export\npage=1\n<UNIX_TIMESTAMP>`
3. The client computes the HMAC-SHA256 hex digest using the UTF-8 bytes of `signingSecret` as the cryptographic key:
   `hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()`
4. The request is dispatched with `x-timestamp` and `x-signature`. Upstream verifies that `|now - x-timestamp|` is within a tolerance window and that the signature matches. If the key expires or rotates, our client invalidates the cached key and retries."

### Q3: How do cumulative counter registers become interval consumption deltas, and how do you handle counter resets?
**Answer**:
"The portal's `/portal/meters/{id}/energy` endpoint reports cumulative active energy register readings (`kwh`). To compute consumption for a 30-minute interval, we sort readings chronologically and calculate the difference:
$$\Delta\text{kWh}_i = \text{kWh}_i - \text{kWh}_{i-1}$$
For the very first reading in any query window, there is no previous baseline reading, so `interval_active_energy_kwh` is explicitly `None` (rather than guessing zero or assuming zero baseline).
If a meter counter regression occurs ($\text{kWh}_i < \text{kWh}_{i-1}$, caused by a meter rollover, hardware replacement, or counter reset), our parser:
1. Sets `interval_active_energy_kwh = None` so fake negative energy is never injected into billing totals.
2. Emits a structured `DataQualityWarning(field='cumulative_active_energy_kwh', message='Counter regression detected...')`.
In our live 50-meter stratified audit, 0 negative regressions were observed; registers are monotonically non-decreasing."

### Q4: Why are inferred hierarchy values acceptable, and how does a consumer distinguish them from raw data?
**Answer**:
"In utility distribution networks, an incomplete hierarchy node breaks tree navigation and rollup aggregations. Because all 403 meters in this discom are partitioned across a closed set of well-defined entities (e.g., Circle 6 always maps to code C-06 on other meters, and code C-01 is known as Circle 1), we infer the missing string from sibling nodes under the same parent with 100% deterministic accuracy.
Crucially, we **never overwrite raw data**:
- Every hierarchy node exposes `code`, `name`, `raw_code`, `raw_name`, and `is_inferred: bool`.
- For meter `J100011`, the response returns:
  `code: "C-06"`, `name: "Circle 6"`, `raw_code: ""`, `raw_name: "Circle 6"`, `is_inferred: true`.
- An accompanying `DataQualityWarning` is attached to `data_quality_warnings`.
A consumer can choose to display the clean inferred tree, or inspect `raw_code`/`is_inferred` to audit raw upstream truth."

### Q5: What breaks if this service runs with multiple workers (`uvicorn --workers 4`)?
**Answer**:
"Three things break or degrade when scaling across multiple worker processes without external state:
1. **Single-flight session login**: `SessionManager._lock` is an `asyncio.Lock()` in process memory. If 4 workers start simultaneously or encounter an expired session, all 4 would independently call `POST /login`, creating redundant logins.
2. **In-Memory Telemetry Cache**: Each worker maintains its own dictionary cache for consumption time-series, leading to cache misses when subsequent requests hit a different worker.
3. **Sync Rate Limiting**: The 60-second cooldown on `POST /api/v1/sync` is stored in an in-memory timestamp (`self._last_sync_time`), so requests distributed across different workers would bypass the in-process cooldown.
To run multi-worker or multi-container in production, we would replace in-memory locks and caches with Redis (using Redlock for single-flight logins and Redis keys for cooldowns and telemetry TTLs)."

### Q6: What happens if the portal rotates its signing secret mid-flight?
**Answer**:
"Our `SessionManager` caches the signing secret for up to 30 minutes. If the portal rotates the secret before then, the next `/portal/export` call returns HTTP 401 or 403.
In `UrjaPortalClient.fetch_meters_bulk`, this error is caught on attempt 1:
1. The client immediately calls `await self.session_manager.invalidate_signing_secret()`.
2. It calls `GET /portal/keys` to retrieve the fresh signing secret.
3. It recomputes the HMAC signature and retries `/portal/export`.
4. If that retry also fails, `SyncService` logs a warning and automatically falls back to paginating `/portal/meters/search`.
Both the secret-invalidation retry and the paged-crawl fallback are covered by automated unit tests in `tests/test_api_mocked.py`."

### Q7: Why were your cache TTLs chosen, and which rationales are OBSERVED versus ASSUMED?
**Answer**:
"- **Meter Master & Hierarchy TTL (1 Hour / 24h SWR)**:
  - *Observed*: Upstream data remained 100% static across all 403 meters throughout our entire investigation.
  - *Assumed*: In power utility operations, distribution topology (substations, feeders, transformers) is structural master data that changes infrequently (weeks/months). 1 hour TTL with 24-hour Stale-While-Revalidate provides sub-millisecond local reads while ensuring eventual consistency.
- **Consumption Telemetry TTL (15 Minutes)**:
  - *Observed*: Active meters report 30-minute block interval load survey records.
  - *Assumed*: A 15-minute TTL guarantees that consumers receive fresh 30-minute readings at twice the collection frequency without hammering the upstream server on every dashboard refresh.
- **Session Cookie TTL (50 Minutes)**:
  - *Observed*: The portal's `__Secure-better-auth.session_token` cookie specifies `Max-Age=3600` (60 minutes).
  - *Rationale*: Proactively renewing the token at 50 minutes (a 10-minute buffer) prevents requests from expiring mid-flight."

### Q8: How did you use AI assistants, and how did you verify your implementation throughout the project?
**Answer**:
"In accordance with the evaluation ground rules, AI assistance was used strictly for high-level guidance, conceptual tips, and unblocking specific error messages (e.g., investigating SvelteKit form CSRF checks). All core reverse-engineering, system architecture, code development, and testing were conducted directly by me.
Every assertion was grounded in empirical evidence:
1. Every reverse-engineered endpoint and wire format was validated with live curl/HTTP scripts, capturing raw request/response headers and payloads into `docs/evidence/`.
2. All parsers and invariants were rigorously tested against actual portal fixtures in `tests/fixtures/`.
3. When assumptions failed (e.g., assuming all serials started with 'SE', or assuming daily-cadence meters were 'legacy' models), I caught them by executing tests and queries against real data, documented the corrections in `WORKLOG.md` and `REFLECTION.md`, and fixed the logic immediately.
4. Final verification included fresh-clone tests following only the `README.md` instructions with real credentials."

### Q9: What would you build with another full engineering day?
**Answer**:
"Three concrete enhancements:
1. **Streaming JSON Ingestion (`ijson`)**: Instead of reading the entire 403-meter JSON export into memory, implement a streaming pipeline parsing and batch-inserting records in chunks of 500, ensuring constant $O(1)$ memory usage if the discom grows to 1,000,000 meters.
2. **Parameterized Downsampling Engine**: Add query parameters (`granularity=hourly`, `granularity=daily`) to `/api/v1/meters/{id}/consumption` that downsample 30-minute interval series into daily or hourly average load curves using SQLite or Pandas.
3. **Distributed Redis Coordination**: Extract `SessionManager`'s lock and token storage into Redis to allow horizontal uvicorn clustering without duplicate logins."

### Q10: What is the single biggest weakness in this submission?
**Answer**:
"The reliance on the internal HMAC `/portal/export` endpoint as the primary synchronization path.
Although we proved it is an official, first-party endpoint called by the portal's own 'Export all meters' button, and we implemented an automated fallback crawl across `/portal/meters/search` if it fails, the export path is still an internal contract. If the utility portal's frontend architecture changes or modifies its signature headers, the bulk path fails and triggers the 23-request fallback crawl, which increases initial sync latency from 250ms to ~7 seconds."

### Q11: How does the fallback crawl operate, and what are its data gaps compared to the export dump?
**Answer**:
"If `/portal/export` fails persistently, `SyncService` paginates `/portal/meters/search` (pages 1 to 21) and `/portal/dts` (pages 1 to 2).
- **Parity**: It achieves 100% record parity (discovering all 403 meters) and captures all primary master attributes (`meterId`, `serialNo`, `make`, `phaseType`, `installStatus`, `dtCode`).
- **Gaps**: Upstream `/portal/meters/search` omits `build_version`, `install_type`, geo-coordinates, and the intermediate 5 hierarchy tiers (`zone`, `circle`, `division`, `subdivision`, `substation`). Resolving those gaps requires 403 individual `/meters/{id}` HTML scrapes and `/geo` lookups, which we deliberately skip during fallback to remain polite."

### Q12: Why did you use an SQL bounding-box prefilter + Haversine distance rather than PostGIS or SpatiaLite?
**Answer**:
"To satisfy the constraint of running locally with zero external dependencies and standard SQLite.
SpatiaLite requires compiling platform-specific C-libraries, and PostGIS requires a running PostgreSQL daemon. For a regional utility dataset (Jaipur metro, ~400–10,000 meters), an indexed bounding box query:
`WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?`
executes in <1ms in SQLite. Computing the exact great-circle Haversine distance in Python across the remaining 20–50 candidate rows takes <0.5ms. It provides sub-millisecond responses without external database infrastructure."

### Q13: What happens on cold start when the SQLite database is empty AND the upstream portal is completely unreachable?
**Answer**:
"1. On startup lifespan, `lifespan(app)` attempts to seed the database via `sync_all(force=True)`. When the portal is unreachable, the network error is caught, logged as a warning, and suppressed, allowing the service to boot cleanly.
2. `/api/v1/health` reports `status: "unhealthy"` because both the portal is unreachable and the local cache has 0 records.
3. Any read request (`GET /api/v1/meters`, `GET /api/v1/hierarchy`, `GET /api/v1/meters/{id}`) attempts lazy synchronization, encounters `UpstreamUnavailableError`, and returns an RFC 7807 `HTTP 503 Service Unavailable` with `application/problem+json`. The app never crashes, and never returns unhandled 500 tracebacks."

### Q14: How did you discover and overcome SvelteKit's CSRF rejection on login?
**Answer**:
"Our initial programmatic `POST /login` form submission returned `HTTP 403 Forbidden` with the body `Cross-site POST form submissions are forbidden`.
By reading the SvelteKit documentation and inspecting the browser's network request headers, I identified that SvelteKit's built-in CSRF protection checks that the `Origin` header matches the request URL's host. Programmatic clients typically omit `Origin` on POSTs. By explicitly supplying `Origin: https://urja-ops.flockenergy.tech` and `Referer: https://urja-ops.flockenergy.tech/login`, the CSRF check passed immediately and returned the session cookie."

### Q15: Why is sub-day timestamp filtering performed in Python rather than delegated to upstream `/portal/meters/{id}/energy`?
**Answer**:
"Through empirical testing recorded in `PROTOCOL.md §3.5`, we observed that the upstream portal's energy endpoint accepts `from` and `to` query parameters, but strictly parses only `YYYY-MM-DD` date strings. If a client passes sub-day ISO timestamps (e.g. `2026-06-25T10:00:00`), the portal completely ignores the time component and returns the entire day's records.
To provide consumers with accurate sub-day time-window semantics, our `energy_parser` parses the date range into UTC-aware `datetime` objects, queries the portal using date boundaries, and filters the resulting readings in Python before computing window consumption summaries."

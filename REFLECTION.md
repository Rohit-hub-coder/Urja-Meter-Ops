# Engineering Reflection & Analysis

*Author: Rohit Kumar (Roll No: 23/SE/129, Delhi Technological University)*  
*Project: Urja Meter Ops API Service*  

---

### 1. Architectural & Domain Assumptions I Made
1. **Timezone & Temporal Semantics**:
   - I assumed the portal timestamps (`DD/MM/YYYY HH:MM`) represent Indian Standard Time (IST, UTC+05:30), reflecting Jaipur, Rajasthan's distribution grid. All timestamps are normalized to ISO-8601 with explicit `+05:30` offsets.
   - I recognized that cumulative telemetry registers (`kwh` and `kvah`) are monotonically increasing counter registers from the meter nameplate. I derived interval consumption as $\Delta\text{kWh} = \text{kWh}_i - \text{kWh}_{i-1}$, setting the first interval to `null` and setting counter resets to `null` with a `DataQualityWarning`.
2. **Topology Stability & Cache TTLs**:
   - I observed that upstream meter data remained static throughout development. I assumed that structural network master data (zones, substations, feeders, DTs) changes infrequently in power utility operations, justifying a 1-hour cache TTL with 24-hour Stale-While-Revalidate (SWR) in local SQLite.
3. **Polite Client Constraints**:
   - Lacking a published upstream SLA, I designed the client to strictly limit concurrency to 2 (`asyncio.Semaphore(2)`), enforce 200–300ms delays between calls, and single-flight authentication re-logins to prevent denial-of-service.
4. **Geospatial Model**:
   - I verified that all 403 meter coordinates lie within Jaipur (Lat 26.78–27.04, Lng 75.66–75.91). I chose an SQL bounding-box prefilter with in-memory Haversine distance, keeping the stack zero-dependency.

---

### 2. The Hardest Challenges & How I Got Unstuck
1. **SvelteKit CSRF Rejection**:
   - *Problem*: My initial programmatic `POST /login` returned `HTTP 403 Forbidden` (`Cross-site POST form submissions are forbidden`).
   - *Investigation*: I inspected browser devtools network traffic and SvelteKit documentation to understand form action CSRF checks. SvelteKit verifies that the `Origin` header matches the request host.
   - *Resolution*: I supplied explicit `Origin: https://urja-ops.flockenergy.tech` and `Referer: https://urja-ops.flockenergy.tech/login` headers, resolving authentication immediately.
2. **Reverse-Engineering the Undocumented Bulk Export Endpoint**:
   - *Problem*: The paged search endpoint (`/portal/meters/search`) only yielded 20 records per page and lacked multi-attribute filtering.
   - *Investigation*: I analyzed client Vite bundle `4.2Bgc2kUI.js` on the `/transformers` route and identified `GET /portal/export` guarded by HMAC-SHA256 headers (`x-timestamp` and `x-signature`).
   - *Resolution*: I reconstructed the signature canonical string (`GET\n/portal/export\npage=1\n<timestamp>`), fetched the signing secret dynamically from `GET /portal/keys`, and proved that this first-party endpoint exports all 403 meters with complete hierarchy and coordinates in ~250ms. I also added automated failover: retrying on 401/403 with a fresh secret, and falling back to paged search if the export fails.

---

### 3. What I Would Improve With Another Day
1. **Streaming JSON Ingestion (`ijson`)**:
   - Currently, the 403-meter JSON export is parsed into memory in ~15ms. To scale to 1,000,000 meters, I would stream and batch records in 500-meter chunks to keep memory usage $O(1)$.
2. **Distributed Redis Coordination for Multi-Worker Scaling**:
   - The current single-flight mutex lock in `SessionManager` uses in-process `asyncio.Lock()`. For multi-worker deployments (`uvicorn --workers 4`), I would migrate locks and telemetry caches to Redis using Redlock.
3. **SQLite R-Tree Spatial Indexing**:
   - For higher density (tens of thousands of meters), I would migrate the 2D bounding-box prefilter to an SQLite virtual table with the `rtree` extension for native SQL spatial lookups.
4. **Parameterized Downsampling Aggregations**:
   - Add `granularity=hourly` or `granularity=daily` query parameters to aggregate 30-minute load curves into daily summaries directly on the server.

---

### 4. Real Mistakes I Made & Corrected
1. **Secret Scanning False Positive in Template**:
   - In `.env.example`, I initially included `contact=operator@[portal_domain]` in the User-Agent placeholder. The pre-commit secret scan caught the portal username. I sanitized it to `operator@example.com` and later to `Rohit-hub-coder/Urja-Meter-Ops` to ensure clean git history.
2. **Premature Assumption About Serial Number Prefixes**:
   - During live smoke testing, I asserted `serial_number.startswith("SE")` based on meter `J100000` (HPL make). The test failed on `J100001` (Genus make, serial `GE84132`). I corrected the test to assert non-empty serial format rather than hardcoding one manufacturer's prefix.
3. **Empty Cache + Unreachable Portal Error Masking**:
   - When the local database was empty and the upstream portal was unreachable, `MeterService.get_meter` caught a generic `Exception` and converted it to `NotFoundError` (404), incorrectly reporting that the meter didn't exist. I corrected the error handling to re-raise `UpstreamUnavailableError` and `UpstreamTimeoutError`, properly returning RFC 7807 503 ProblemDetails.
4. **Unverified Hypothesis on Daily-Cadence Meters**:
   - I initially hypothesized that daily-cadence meters represented older hardware or "legacy billing meters". When correlating against the 403-meter database, exactly 9 of the 18 sampled daily meters were `build_version: "v2"` and 9 were `build_version: "legacy"`. Because the data did not support the hypothesis, I reworded the documentation to state the hypothesis was unverified and not supported by data.

---

### 5. What I Criticise in My Own Submission
1. **In-Memory Single-Worker Concurrency Locks**:
   - The single-flight mutex in `SessionManager` is an in-process lock. In a multi-worker production deployment (`uvicorn --workers 4`), each process manages its own independent session. A shared Redis distributed lock is required for clustering.
2. **Upstream Telemetry Sub-Day Filtering Waste**:
   - Upstream `/portal/meters/{id}/energy` ignores sub-day timestamps in `from`/`to` parameters. When a client queries a 2-hour window, our service fetches the entire day's records and filters in Python, wasting upstream bandwidth.
3. **Consumption Granularity Agnosticism**:
   - The API currently parses and summarizes telemetry as delivered by the portal (30-min or daily). Parameterized downsampling (e.g. `granularity=daily`) is not yet parameterized via API query parameter.

---

### 6. AI-Use Disclosure & Verification Strategy
- **Agent Tool & Model Used**: Antigravity coding assistant powered by Gemini 3.8 Flash.
- **Role of Claude (Anthropic)**: Claude was used in a separate chat to draft the initial agent prompt, review the agent's progress reports, suggest verification checks, and draft the evaluation rubric. Claude never had access to the repository, codebase, or portal—only the take-home assignment PDF and text reports pasted by me.
- **Verification Strategy**: Zero claims were accepted without empirical execution. Every single portal wire format, endpoint behavior, and edge case was empirically probed against the live portal, captured into `docs/evidence/`, saved as offline fixtures in `tests/fixtures/`, and verified with automated test suites passing locally.

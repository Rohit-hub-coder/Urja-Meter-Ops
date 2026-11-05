# Engineering Reflection & Analysis

---

### 1. Assumptions Made
1. **Timezone & Temporal Semantics**:
   - The upstream portal timestamps (`DD/MM/YYYY HH:MM`) correspond to Indian Standard Time (IST, UTC+05:30) given the discom's geographic deployment in Jaipur, Rajasthan.
   - Cumulative telemetry registers (`kwh` and `kvah`) are monotonically increasing counter registers from the meter nameplate, rather than interval delta consumption. Interval consumption is derived by calculating differences between successive 30-minute readings.
2. **Topology & Master Data Stability**:
   - The distribution hierarchy (Zone &rarr; Circle &rarr; Division &rarr; Subdivision &rarr; Substation &rarr; Feeder &rarr; DT &rarr; Meter) is structural master data with low turnover. A 1-hour cache TTL with 24-hour Stale-While-Revalidate (SWR) is safe for operational queries.
3. **Upstream Rate Constraints & Single Tenant**:
   - The portal has no published SLA or rate limits. Operating as a polite client with concurrency bounded to 2 (`asyncio.Semaphore(2)`), 200–300ms delays, and single-flight authentication prevents upstream disruption.
4. **Spatial Coordinates**:
   - All coordinates fall strictly within WGS 84 bounds around the Jaipur metro region (Lat 26.78–27.04, Lng 75.66–75.91). Haversine distance with bounding-box prefiltering is exact and fast for regional distribution networks.

---

### 2. The Hardest Part & How I Got Unstuck
1. **SvelteKit CSRF Rejection**:
   - *Problem*: Initial programmatic `POST /login` form submissions returned an immediate `HTTP 403 Forbidden` (`Cross-site POST form submissions are forbidden`).
   - *Investigation*: SvelteKit uses automatic origin-checking for all POST form actions (`use:enhance` / native forms).
   - *Solution*: Explicitly supplied `Origin: https://urja-ops.flockenergy.tech` and `Referer: https://urja-ops.flockenergy.tech/login`.
2. **Reverse-Engineering the Undocumented Bulk Export Endpoint**:
   - *Problem*: Paged search (`/portal/meters/search`) only supported 20 items per page and filtered solely on `meterId` or `serialNo` substring without multi-attribute filters.
   - *Investigation*: Decompiled client-side Vite chunks (`4.2Bgc2kUI.js` on the Transformers page) and discovered `GET /portal/export` guarded by HMAC-SHA256 headers (`x-timestamp` and `x-signature`).
   - *Solution*: Identified that the signing secret is obtained dynamically from `GET /portal/keys`, reconstructed the canonical string to sign (`GET\n/portal/export\npage=1\n<timestamp>`), and confirmed that this bulk endpoint returns all 403 meters with complete hierarchy and geo coordinates in a single 250ms call.

---

### 3. What I'd Improve With Another Day
1. **Streaming JSON Ingestion (`ijson`)**:
   - For 403 meters, loading the JSON payload into memory and batch-inserting into SQLite executes in ~15ms. If the grid scale expands to 1,000,000 meters, memory pressure would spike. I would implement streaming JSON parser pipelines (`ijson`) writing chunked batches directly to SQLite.
2. **Distributed Cache & State Synchronization**:
   - Currently, consumption telemetry uses an in-memory TTL cache, and the meter index is stored in local SQLite. For multi-replica deployments behind a load balancer, I would transition the cache and mutex locks to Redis with Redlock single-flight deduplication.
3. **SQLite R-Tree Spatial Indexing**:
   - The current bounding-box SQL prefilter + in-memory Haversine formula is fast for sub-10,000 meters (<2ms response). At higher densities, creating an SQLite virtual table using the `rtree` extension would allow native 2D bounding box spatial lookups directly inside the SQL engine.

---

### 4. A Real Mistake Made & Corrected
1. **Secret Scanning False Positive in Template**:
   - When creating `.env.example`, I initially included `contact=operator@[portal_domain]` in the User-Agent placeholder. The pre-commit secret scan immediately caught the portal username. Even though it was only an example file, I sanitized it to `operator@example.com` to guarantee 100% clean secret scanning across all git history.
2. **Premature Assumption About Serial Number Prefixes**:
   - During live smoke test authoring, I asserted `serial_number.startswith("SE")` based on the first meter `J100000` (HPL make). The live test failed on `J100001` with `AssertionError: 'GE84132'.startswith('SE')` because Genus meters use the `GE` prefix. I corrected the invariant to validate format cleanliness rather than hardcoding a single manufacturer's prefix.

---

### 5. What I'd Criticise in My Own Submission
1. **Consumption Granularity Agnosticism**:
   - The upstream portal only provides half-hourly (30-min) telemetry intervals. Although our API cleanly parses and summarizes these intervals, custom downsampling (e.g. hourly or daily bucketing) is currently done client-side or on the full window rather than parameterized via a `granularity=daily` aggregation engine.
2. **Synchronous Export Signature Rotation**:
   - The signing secret from `/portal/keys` is cached for 30 minutes. If the portal rotates its key without notice, a request could fail with 401/403 before our cache expires. Adding an automatic invalidation and retry on signature failure would eliminate this rare edge case.

---

### 6. AI-Use Disclosure & Verification Strategy
- **Tools Used**: Gemini 3.8 Flash (High) via Antigravity agentic coding assistant was utilized as a senior pair programmer for reverse-engineering investigation, architecture implementation, test authoring, and documentation. Claude (Anthropic) was used to draft and review the initial agent prompt.
- **Verification Strategy**: Zero claims were accepted without empirical execution. Every single portal wire format, endpoint behavior, and edge case was empirically probed against the live portal, captured into `docs/evidence/`, saved as offline fixtures in `tests/fixtures/`, and verified with automated test suites passing locally.

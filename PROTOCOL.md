# Urja Meter Ops: Reverse-Engineered Wire Protocol Specification

> **Status**: Verified Against Live Portal (`https://urja-ops.flockenergy.tech`)  
> **Investigation Date**: November 5, 2026  
> **Evidence Directory**: `docs/evidence/`  
> **Offline Fixtures**: `tests/fixtures/`

---

## 1. System Overview

| Attribute | Specification | Evidence / Label |
|---|---|---|
| **Portal Platform** | SvelteKit (Vite bundle, client-side routing + SSR) | **[OBSERVED]** Header `x-sveltekit-page: true`, chunks in `/_app/immutable/` |
| **Authentication Engine** | `better-auth` session management | **[OBSERVED]** Cookie name `__Secure-better-auth.session_token` |
| **Total Meter Inventory** | Exactly 403 meters (`J100000` to `J100402`) | **[OBSERVED]** `docs/evidence/07_export_page1.json` (`total: 403`) |
| **Distribution Transformers** | Exactly 40 DT units (`DT-001` to `DT-040`) | **[OBSERVED]** `docs/evidence/06_dts_page1.json` (`total: 40`) |
| **Geographic Scope** | Jaipur Metropolitan Region, Rajasthan, India | **[OBSERVED]** Coordinates bounding box: Lat 26.7881–27.0369, Lng 75.6625–75.9122 |

---

## 2. Authentication, CSRF & Session Lifecycle

### 2.1 Login Flow
* **URL**: `POST /login`
* **Content-Type**: `application/x-www-form-urlencoded`
* **Form Fields**: `email` (string), `password` (string).
* **Required CSRF Headers**:
  ```http
  Origin: https://urja-ops.flockenergy.tech
  Referer: https://urja-ops.flockenergy.tech/login
  ```
  * **[OBSERVED]**: If `Origin` is missing or mismatched, the portal returns **HTTP 403 Forbidden** (`Cross-site POST form submissions are forbidden`).
* **Success Response**:
  * With `Accept: application/json` or fetch:
    * Status: `200 OK`
    * Body: `{"type":"redirect","status":303,"location":"/meters"}`
  * With `Accept: text/html`:
    * Status: `303 See Other`
    * Header `Location: /meters`
  * Sets Cookie: `__Secure-better-auth.session_token=<token>; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax`
* **Failure Response**:
  * Status: `200 OK` (SvelteKit action JSON failure)
  * Body: `{"type":"failure","status":401,"data":"[{\"email\":1,\"error\":2},\"...\",\"Invalid email or password.\"]"}`

### 2.2 Session Expiry & Invalid Tokens
* **Session Lifetime**: Exactly 3600 seconds (1 hour) as specified by `Max-Age=3600`.
* **Expired / Missing Cookie Behavior**:
  * **[OBSERVED]**: Requesting any protected route (`/meters`, `/transformers`, `/portal/meters/...`) without a valid session cookie returns **HTTP 302 Found** with `Location: /login` (silent redirect).
  * If the HTTP client follows redirects, it lands on `/login` with `HTTP 200 OK` and the login HTML form.
  * **Architectural Rule**: The API client must detect HTTP 302 redirects to `/login` (or HTML landing on `/login`) as an expired session and trigger an atomic single-flight re-login.

### 2.3 Sign-Out
* **URL**: `POST /api/auth/sign-out`
* **Headers**: `Origin: https://urja-ops.flockenergy.tech`
* **Effect**: Invalidates server session token and clears client cookie.

---

## 3. Discovered Endpoints & Wire Protocols

### 3.1 Bulk Export: `GET /portal/export` (Primary Synchronization Lever)
* **Status**: **[OBSERVED]** Discovered in SvelteKit client bundle `4.2Bgc2kUI.js`.
* **Security Protocol**: Signed using HMAC-SHA256 with a dynamic secret.
  1. Fetch signing secret from `GET /portal/keys`:
     ```json
     { "data": { "signingSecret": "[REDACTED_SIGNING_SECRET]" } }
     ```
  2. Construct signing payload string:
     ```
     GET\n/portal/export\npage=1\n<UNIX_TIMESTAMP>
     ```
  3. Compute HMAC-SHA256 hex digest using `signingSecret`.
  4. Send request with headers:
     ```http
     x-timestamp: <UNIX_TIMESTAMP>
     x-signature: <HEX_DIGEST>
     ```
* **Payload Structure**:
  Returns all **403 meters in a single JSON response** (`total: 403`), complete with:
  * Meter master: `meterId`, `serialNo`, `make`, `phaseType`, `installStatus`, `installType`, `build`, `dtCode`.
  * Geo coordinates: `geo: { "lat": 26.93896..., "lng": 75.83095... }` (floats).
  * Hierarchy: 7 nested objects (`zone`, `circle`, `division`, `subdivision`, `substation`, `feeder`, `dt`), each with `name` and `code`.
* **Pagination & Query Parameters [OBSERVED]**:
  * The query parameter `page=1` is hardcoded in the portal's client script, but the upstream server ignores `page`.
  * The response keys are strictly `{"data": [...], "total": 403}`.
  * There is **no pagination metadata** (no `page`, `limit`, `total_pages`, or `has_next` fields). The endpoint always dumps the full 403-meter dataset in one call (~250ms).

### 3.1.1 Export Legitimacy & First-Party Verification
* **Source Bundle**: Located in the portal's production client-side SvelteKit bundle `/_app/immutable/nodes/4.2Bgc2kUI.js` (the component backing the `/transformers` UI route).
* **De-minified Code Excerpt**: The snippet below is a formatted, de-minified excerpt of the client bundle code (minified single-letter identifiers expanded for clarity):
  ```javascript
  // HMAC-SHA256 signature generator embedded in the portal client bundle:
  async function C(method, path, query, secret) {
    let ts = String(Math.floor(Date.now() / 1e3));
    let payload = [method, path, query, ts].join("\n");
    let key = await crypto.subtle.importKey(
      "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
    );
    let sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
    return {
      timestamp: ts,
      signature: [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("")
    };
  }

  // First-party UI click handler for 'Export all meters':
  async function F() {
    let secret = (await (await fetch("/portal/keys")).json()).data.signingSecret;
    let query = "page=1";
    let { timestamp: ts, signature: sig } = await C("GET", "/portal/export", query, secret);
    let res = await fetch("/portal/export?" + query, {
      headers: { "x-timestamp": ts, "x-signature": sig }
    });
    let data = await res.json();
    let blob = new Blob([JSON.stringify(data.data, null, 2)], { type: "application/json" });
    // Triggers meter-export.json download in browser
  }
  ```
* **No Access Control Bypassed**:
  - The endpoint is a standard client capability triggered by clicking "Export all meters" on `/transformers`.
  - Both `/portal/keys` and `/portal/export` execute within the standard operator session (`__Secure-better-auth.session_token`).
  - No privilege escalation, undocumented tokens, or security controls were bypassed.
* **Polite Operational Safeguards**:
  - Strictly read-only operations.
  - Concurrency is throttled to 2 concurrent in-flight requests maximum (`asyncio.Semaphore(2)`).
  - Manual sync invocations (`POST /api/v1/sync`) enforce a mandatory 60-second cooldown period, preventing repeated hits to the portal.

### 3.1.2 Bulk Export vs. Fallback Paged Crawl Completeness Comparison
If `/portal/export` is unavailable or returns 401/403, the synchronization service falls back to paginating `/portal/meters/search` and merging with `/portal/dts`. The completeness tradeoffs between the two discovery methods are quantified below:

| Feature Dimension | Bulk Path (`/portal/export`) | Fallback Paged Crawl (`/portal/meters/search` + `/portal/dts`) | Completeness & Parity Analysis |
|---|---|---|---|
| **Network Cost** | 1 request (~250ms) | 23 requests (21 pages search + 2 pages DTs, ~7-8s) | 23× more round-trips; higher latency |
| **Meter Population** | 403 / 403 meters (100%) | 403 / 403 meters (100%) | **Full parity**: all 403 meters discovered |
| **Master Identity** | `meterId`, `serialNo`, `make`, `dtCode`, `phaseType`, `installStatus` | `meterId`, `serialNo`, `make`, `dtCode`, `phaseType`, `installStatus` | **Exact parity** across all master attributes |
| **Firmware & Install Type** | `build` ("legacy", "v2"), `installType` ("Whole Current", "CT Operated") | Omitted upstream (`null`) | **Gap**: requires individual `/meters/{id}` HTML detail scrapes |
| **Geo Coordinates** | `latitude`, `longitude` (WGS 84 float for all 403 meters) | Omitted upstream (`null`) | **Gap**: requires 403 separate `/portal/meters/{id}/geo` calls |
| **Hierarchy Topology** | Complete 7-tier nested tree (`zone` down to `dt`) | `dtCode` provided; resolves to DT name/feeder via `/portal/dts` | **Partial**: top 5 tiers (`zone` through `substation`) absent unless inferred from peer DTs |

### 3.2 Meters Search: `GET /portal/meters/search`
* **Query Parameters**:
  * `q`: Search string (searches substring of `meterId` or `serialNo`).
  * `page`: 1-based page index.
* **Limitations [OBSERVED]**:
  * Fixed page size of 20 items. `limit` parameter is completely ignored by upstream.
  * Does NOT support filtering by `make`, `dtCode`, `installStatus`, or `phaseType`.

### 3.3 Distribution Transformers: `GET /portal/dts`
* **Query Parameters**: `page=1`, `page=2`.
* **Page Size**: Exactly 20 DTs per page, total 40 DTs (`DT-001` to `DT-040`).
* **Fields**: `code`, `name`, `feederCode`, `capacityKva` (e.g. 100 kVA).

### 3.4 Meter Location: `GET /portal/meters/{meterId}/geo`
* **Response**:
  ```json
  { "data": { "latitude": "26.938961002479868", "longitude": "75.83095696146852" } }
  ```
* **Type Quirk [OBSERVED]**: Coordinates are strings here, compared to floats in `/portal/export`.
* **404 Behavior**: Returns `404 Not Found` with `{"error":"not_found","message":"Meter not found"}`.

### 3.5 Meter Telemetry: `GET /portal/meters/{meterId}/energy`
* **Response**: Array of load survey records.
* **Fields per record**:
  * `timestamp`: `"DD/MM/YYYY HH:MM"` (e.g. `"24/06/2026 00:00"`).
  * `kwh`: Cumulative active energy register reading (string float, e.g. `"48439.16"`).
  * `kvah`: Cumulative apparent energy register reading (string float, e.g. `"52314.29"`).
  * `voltR`: Phase R voltage in Volts (string int, e.g. `"229"`).
* **Supported Query Parameters [OBSERVED]**:
  * `from=YYYY-MM-DD`: Earliest date boundary.
  * `to=YYYY-MM-DD`: Latest date boundary.
* **Limitations [OBSERVED]**: Sub-day ISO timestamps (e.g. `2026-06-25T12:00:00`) are ignored by upstream and return the default full window.

### 3.5.1 Empirical Telemetry Census (Stratified Sample of 50 Meters)
An automated rate-limited audit (`scripts/telemetry_census.py`, concurrency 2, delay 250ms) evaluated 50 meters chosen via stratified sampling across all 30 permutations of 5 manufacturers (`Allied`, `Genus`, `HPL`, `L&T`, `Secure`), 2 phase types (`single`, `three`), and 3 lifecycle states (`Installed`, `Faulty`, `Decommissioned`). Evidence saved to `docs/evidence/13_telemetry_census.md`.

> **Note on Sampling**: These metrics reflect observations across a non-random stratified sample of 50 meters designed to cover edge combinations; they are **not population-wide proportions**.

* **Observed Sample Metrics [OBSERVED in Sample]**:
  * **Dual Cadence Breakdown**:
    * **30-Minute Cadence**: 32 of 50 sampled meters report 30-minute block interval telemetry (typically 337 readings across a 7-day span).
    * **Daily Midnight Snapshot Cadence**: 18 of 50 sampled meters report exactly one reading per day at midnight (`00:00:00`), totaling 8 daily snapshot readings.
  * **Negative Deltas / Counter Regressions**: Exactly 0 negative deltas observed across the 50 sampled meters. Registers are monotonically non-decreasing.
  * **Timestamp Continuity & Duplication**: Exactly 0 timestamp gaps (>1.5× expected cadence) and 0 duplicate timestamps observed.
  * **Decommissioned Meters Telemetry Retention**: 17 of 17 sampled decommissioned meters (100%) still return full historical telemetry on this endpoint.
* **Correlation Analysis for Daily Cadence [OBSERVED]**:
  * **Build Version Correlation**: Exactly 9 daily meters in the sample are `build_version: "v2"` and 9 are `build_version: "legacy"` (the same ~50/50 split observed in 30-minute meters). There is **no observed correlation** between daily cadence and firmware `build_version`.
  * **Manufacturer Make**: Daily meters appear across all 5 makes (Allied: 5, Secure: 4, HPL: 4, L&T: 3, Genus: 2).
  * **Install Status**: 16 of the 18 daily meters (88.9%) are marked `Decommissioned` (10) or `Faulty` (6); only 2 are `Installed`.
  * *Domain Hypothesis [ASSUMED - NOT SUPPORTED BY DATA]*: The initial hypothesis that daily-cadence meters represent older hardware or "legacy billing meters" is **not supported by data**, since half of the daily-cadence meters run `build_version: "v2"`. Instead, daily cadence may reflect meters placed into daily-snapshot mode upon entering Faulty/Decommissioned status, or meter profiles with lower reporting tiers.
  * *Decommissioned meter data retention [ASSUMED]*: Decommissioning reflects an administrative status flag in the utility's outage/inventory database; historical telemetry is retained in the historical time-series database.

---

## 4. Hierarchy Structure & Data Quirks Census

### 4.1 Topology
The network hierarchy has 7 explicit levels:
```
Zone (3)
 └── Circle (6)
      └── Division (10)
           └── Subdivision (13)
                └── Substation (18)
                     └── Feeder (28)
                          └── Distribution Transformer [DT] (40)
                               └── Meter (403)
```

### 4.2 Quantified Data Anomalies (Census of all 403 Meters)

| Quirk / Anomaly | Count | Affected Meters | Handling / Normalization Strategy |
|---|---|---|---|
| **Circle name present, code empty `""`** | 6 (1.5%) | `J100011`, `J100074`, `J100097`, `J100116`, `J100265`, `J100373` | Inferred from peer nodes sharing name (e.g. "Circle 6" -> `C-06`); flag in `data_quality`. |
| **Circle code present, name empty `""`** | 5 (1.2%) | `J100218`, `J100248`, `J100306`, `J100370`, `J100371` | Inferred from peer nodes sharing code (e.g. `C-05` -> "Circle 5"); flag in `data_quality`. |
| **Feeder name present, code empty `""`** | 5 (1.2%) | `J100044`, `J100078`, `J100134`, `J100210`, `J100268` | Inferred from peer nodes / DT feeder mapping; flag in `data_quality`. |
| **Feeder code present, name empty `""`** | 3 (0.7%) | `J100162`, `J100257`, `J100372` | Inferred from peer nodes; flag in `data_quality`. |
| **Substation name present, code empty `""`** | 3 (0.7%) | `J100153`, `J100228`, `J100302` | Inferred from peer nodes; flag in `data_quality`. |
| **Total Incomplete Hierarchy Nodes** | **22 (5.46%)** | Unique set of 22 meters | Repaired transparently via topology dictionary; exposed with quality warning. |
| **Orphaned Meters** | **0 (0.0%)** | None | All 403 meters link to a valid DT in `/portal/dts`. |
| **Multiple Parents for DT** | **0 (0.0%)** | None | Every DT has a unique parent feeder. |
| **Invalid / Null Coordinates** | **0 (0.0%)** | None | 403 / 403 have valid lat/lng inside Jaipur metro region. |
| **Swapped Coordinates** | **0 (0.0%)** | None | Latitudes in 26.78–27.04, Longitudes in 75.66–75.91. |

---

## 5. Performance & Operational Constraints

* **Upstream Latencies [OBSERVED]**:
  * Login (`POST /login`): ~300 ms
  * Paged Search / DTs / Geo: ~40–50 ms
  * Consumption Telemetry: ~55 ms
  * Bulk Export (all 403 meters): ~250 ms
* **Polite Client Enforcement**:
  * Concurrency limit: Maximum 2 concurrent connections (`asyncio.Semaphore(2)`).
  * Rate delay: 300 ms between sequential page crawls.
  * Upstream Request Timeout: 15.0 seconds.
  * Backoff: Exponential backoff with jitter on HTTP 429 or 5xx.

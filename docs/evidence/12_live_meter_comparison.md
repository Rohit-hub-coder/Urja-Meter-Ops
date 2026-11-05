# Live Portal vs. API Side-by-Side Verification Evidence

> **Execution Date**: November 5, 2026  
> **Target Portal**: `https://urja-ops.flockenergy.tech`  
> **Verification Method**: Empirical field-by-field comparison between raw legacy portal HTML/JSON endpoints and normalized API responses for 3 sample meters.  
> **Note**: This comparison compares our API's normalized output against raw legacy portal responses (SSR HTML from `/meters/{id}` and JSON from `/portal/meters/{id}/energy`).

---

## Meter Comparison: `J100000`

### 1. Master & Nameplate Attributes

| Field Name | Raw Portal Endpoint / SSR HTML Value | Our API Normalized Output | Match Status |
|---|---|---|:---:|
| **Meter ID** | `J100000` | `J100000` | **EXACT MATCH** |
| **Serial Number** | `SE33962` | `SE33962` | **EXACT MATCH** |
| **Manufacturer Make** | `HPL` | `HPL` | **EXACT MATCH** |
| **Phase Configuration** | `single` | `single` | **EXACT MATCH** |
| **Installation Status** | `Decommissioned` | `Decommissioned` | **EXACT MATCH** |
| **Installation Type** | `Whole Current` | `Whole Current` | **EXACT MATCH** |
| **Latitude** | `26.938961002479868` | `26.938961002479868` | **EXACT MATCH** |
| **Longitude** | `75.83095696146852` | `75.83095696146852` | **EXACT MATCH** |
| **Distribution Transformer** | `DT Code: DT-001` | `Malviya Nagar DT 1 (DT-001)` | **NORMALIZED** |

### 2. Telemetry & Telemetry Summary (Time Window: 23/06/2026 to 30/06/2026)

| Metric | Raw Portal Endpoint (`/portal/meters/J100000/energy`) | Our API (`/api/v1/meters/J100000/consumption`) | Match Status |
|---|---|---|:---:|
| **Readings Count** | `337` | `337` | **EXACT MATCH** |
| **First Reading Timestamp** | `23/06/2026 23:30` (legacy string) | `2026-06-23T23:30:00+05:30` (ISO-8601 IST) | **NORMALIZED** |
| **First Reading kWh** | `48438.74` kWh | `48438.74` kWh | **EXACT MATCH** |
| **First Reading Voltage** | `226` V | `226.0` V | **EXACT MATCH** |
| **Last Reading Timestamp** | `30/06/2026 23:30` (legacy string) | `2026-06-30T23:30:00+05:30` (ISO-8601 IST) | **NORMALIZED** |
| **Last Reading kWh** | `48580.79` kWh | `48580.79` kWh | **EXACT MATCH** |
| **Total Energy Consumed (window)** | Computed difference: `142.05` kWh | `142.05` kWh | **DERIVED** |
| **Average Voltage (window)** | Computed arithmetic mean: `229.83` V | `229.83` V | **DERIVED** |

---
## Meter Comparison: `J100001`

### 1. Master & Nameplate Attributes

| Field Name | Raw Portal Endpoint / SSR HTML Value | Our API Normalized Output | Match Status |
|---|---|---|:---:|
| **Meter ID** | `J100001` | `J100001` | **EXACT MATCH** |
| **Serial Number** | `GE84132` | `GE84132` | **EXACT MATCH** |
| **Manufacturer Make** | `L&T` | `L&T` | **EXACT MATCH** |
| **Phase Configuration** | `single` | `single` | **EXACT MATCH** |
| **Installation Status** | `Installed` | `Installed` | **EXACT MATCH** |
| **Installation Type** | `CT Operated` | `CT Operated` | **EXACT MATCH** |
| **Latitude** | `26.822136543835608` | `26.822136543835608` | **EXACT MATCH** |
| **Longitude** | `75.90718190602279` | `75.90718190602279` | **EXACT MATCH** |
| **Distribution Transformer** | `DT Code: DT-002` | `Mansarovar DT 2 (DT-002)` | **NORMALIZED** |

### 2. Telemetry & Telemetry Summary (Time Window: 23/06/2026 to 30/06/2026)

| Metric | Raw Portal Endpoint (`/portal/meters/J100001/energy`) | Our API (`/api/v1/meters/J100001/consumption`) | Match Status |
|---|---|---|:---:|
| **Readings Count** | `337` | `337` | **EXACT MATCH** |
| **First Reading Timestamp** | `23/06/2026 23:30` (legacy string) | `2026-06-23T23:30:00+05:30` (ISO-8601 IST) | **NORMALIZED** |
| **First Reading kWh** | `42594.05` kWh | `42594.05` kWh | **EXACT MATCH** |
| **First Reading Voltage** | `231` V | `231.0` V | **EXACT MATCH** |
| **Last Reading Timestamp** | `30/06/2026 23:30` (legacy string) | `2026-06-30T23:30:00+05:30` (ISO-8601 IST) | **NORMALIZED** |
| **Last Reading kWh** | `42732.85` kWh | `42732.85` kWh | **EXACT MATCH** |
| **Total Energy Consumed (window)** | Computed difference: `138.80` kWh | `138.8` kWh | **DERIVED** |
| **Average Voltage (window)** | Computed arithmetic mean: `230.3` V | `230.3` V | **DERIVED** |

---
## Meter Comparison: `J100002`

### 1. Master & Nameplate Attributes

| Field Name | Raw Portal Endpoint / SSR HTML Value | Our API Normalized Output | Match Status |
|---|---|---|:---:|
| **Meter ID** | `J100002` | `J100002` | **EXACT MATCH** |
| **Serial Number** | `AL28136` | `AL28136` | **EXACT MATCH** |
| **Manufacturer Make** | `L&T` | `L&T` | **EXACT MATCH** |
| **Phase Configuration** | `single` | `single` | **EXACT MATCH** |
| **Installation Status** | `Installed` | `Installed` | **EXACT MATCH** |
| **Installation Type** | `CT Operated` | `CT Operated` | **EXACT MATCH** |
| **Latitude** | `26.840224163401967` | `26.840224163401967` | **EXACT MATCH** |
| **Longitude** | `75.71461868999545` | `75.71461868999545` | **EXACT MATCH** |
| **Distribution Transformer** | `DT Code: DT-003` | `Vaishali DT 3 (DT-003)` | **NORMALIZED** |

### 2. Telemetry & Telemetry Summary (Time Window: 23/06/2026 to 30/06/2026)

| Metric | Raw Portal Endpoint (`/portal/meters/J100002/energy`) | Our API (`/api/v1/meters/J100002/consumption`) | Match Status |
|---|---|---|:---:|
| **Readings Count** | `337` | `337` | **EXACT MATCH** |
| **First Reading Timestamp** | `23/06/2026 23:30` (legacy string) | `2026-06-23T23:30:00+05:30` (ISO-8601 IST) | **NORMALIZED** |
| **First Reading kWh** | `6850.32` kWh | `6850.32` kWh | **EXACT MATCH** |
| **First Reading Voltage** | `227` V | `227.0` V | **EXACT MATCH** |
| **Last Reading Timestamp** | `30/06/2026 23:30` (legacy string) | `2026-06-30T23:30:00+05:30` (ISO-8601 IST) | **NORMALIZED** |
| **Last Reading kWh** | `7002.59` kWh | `7002.59` kWh | **EXACT MATCH** |
| **Total Energy Consumed (window)** | Computed difference: `152.27` kWh | `152.27` kWh | **DERIVED** |
| **Average Voltage (window)** | Computed arithmetic mean: `230.56` V | `230.56` V | **DERIVED** |

---

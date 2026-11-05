# Evidence 13: Telemetry Census across 50 Stratified Meters

**Date Executed**: 2026-11-05 12:12:00
**Methodology**: Polite rate-limited audit (concurrency=2, inter-request delay=250ms) across 50 meters.
Stratification guarantees full coverage across all 30 combinations of:
- **5 Makes**: Allied, Genus, HPL, L&T, Secure
- **2 Phase Types**: single, three
- **3 Install Statuses**: Installed, Faulty, Decommissioned

## 1. High-Level Summary Statistics

- **Total Meters Sampled**: 50
- **Cadence: Daily (Midnight)**: 18 meters (36.0%)
- **Cadence: 30-minute**: 32 meters (64.0%)
- **Negative Deltas (Counter Resets / Rollovers)**: 0 meters
- **Timestamp Gaps**: 0 meters
- **Duplicate Timestamps**: 0 meters
- **Decommissioned Meters Retaining Telemetry**: 17 / 17 (100%)

## 2. Key Findings & Empirical Observations

1. **Dual Cadence Profiles [OBSERVED]**:
   - **30-Minute Cadence**: Typical active smart meters report 30-minute block interval telemetry (typically ~337 readings spanning ~7 days).
   - **Daily Midnight Snapshot Cadence**: A subset of meters report exactly one reading per day at midnight (`00:00:00`), typically ~8 daily readings.
2. **Negative Deltas / Counter Resets [OBSERVED]**:
   - Exactly 0 negative deltas observed in the 50-meter sample. Cumulative kWh/kVAh registers are strictly non-decreasing across all observed intervals.
3. **Timestamp Gaps & Continuity [OBSERVED]**:
   - Timestamp gaps (>1.5x expected cadence) observed in 0 meters.
4. **Duplicate Timestamps [OBSERVED]**:
   - Duplicate timestamps observed: 0. Upstream energy records maintain unique timestamps per meter.
5. **Decommissioned Meters [OBSERVED]**:
   - 100% of sampled decommissioned meters still return historical telemetry on `/portal/meters/{id}/energy`.
   - *Interpretation [ASSUMED]*: Decommissioning is a logical administrative status update in the utility OMS/MDM and does not purge historical meter readings.

## 3. Sample Meter Telemetry Audit Table (50 Meters)

| Meter ID | Make | Phase | Status | Cadence | Readings | First kWh | Last kWh | Gaps | Neg. Deltas |
|----------|------|-------|--------|---------|----------|-----------|----------|------|-------------|
| `J100130` | Allied | single | Decommissioned | Daily (Midnight) | 8 | 14438.28 | 14565.89 | 0 | 0 |
| `J100026` | Allied | single | Faulty | 30-minute | 337 | 18401.18 | 18505.02 | 0 | 0 |
| `J100012` | Allied | single | Installed | 30-minute | 337 | 7513.51 | 7670.1 | 0 | 0 |
| `J100256` | Allied | three | Decommissioned | Daily (Midnight) | 8 | 2678.19 | 2770.16 | 0 | 0 |
| `J100005` | Allied | three | Faulty | 30-minute | 337 | 3662.84 | 3773.58 | 0 | 0 |
| `J100013` | Allied | three | Installed | 30-minute | 337 | 28025.5 | 28145.26 | 0 | 0 |
| `J100007` | Genus | single | Decommissioned | 30-minute | 337 | 30841.97 | 30957.0 | 0 | 0 |
| `J100004` | Genus | single | Faulty | 30-minute | 337 | 20403.4 | 20474.44 | 0 | 0 |
| `J100003` | Genus | single | Installed | 30-minute | 337 | 6315.48 | 6441.01 | 0 | 0 |
| `J100025` | Genus | three | Decommissioned | 30-minute | 337 | 48228.18 | 48299.45 | 0 | 0 |
| `J100014` | Genus | three | Faulty | 30-minute | 337 | 36520.66 | 36606.07 | 0 | 0 |
| `J100016` | Genus | three | Installed | 30-minute | 337 | 43819.85 | 43897.11 | 0 | 0 |
| `J100000` | HPL | single | Decommissioned | 30-minute | 337 | 48438.74 | 48580.79 | 0 | 0 |
| `J100018` | HPL | single | Faulty | 30-minute | 337 | 2525.15 | 2575.72 | 0 | 0 |
| `J100024` | HPL | single | Installed | 30-minute | 337 | 36026.38 | 36149.75 | 0 | 0 |
| `J100011` | HPL | three | Decommissioned | 30-minute | 337 | 14377.5 | 14509.13 | 0 | 0 |
| `J100117` | HPL | three | Faulty | Daily (Midnight) | 8 | 6045.56 | 6156.82 | 0 | 0 |
| `J100015` | HPL | three | Installed | 30-minute | 337 | 14311.01 | 14379.49 | 0 | 0 |
| `J100019` | L&T | single | Decommissioned | 30-minute | 337 | 44756.94 | 44935.88 | 0 | 0 |
| `J100022` | L&T | single | Faulty | 30-minute | 337 | 46665.46 | 46750.82 | 0 | 0 |
| `J100001` | L&T | single | Installed | 30-minute | 337 | 42594.05 | 42732.85 | 0 | 0 |
| `J100090` | L&T | three | Decommissioned | Daily (Midnight) | 8 | 12740.95 | 12854.16 | 0 | 0 |
| `J100105` | L&T | three | Faulty | Daily (Midnight) | 8 | 35363.27 | 35519.18 | 0 | 0 |
| `J100017` | L&T | three | Installed | 30-minute | 337 | 20606.65 | 20777.28 | 0 | 0 |
| `J100046` | Secure | single | Decommissioned | Daily (Midnight) | 8 | 26545.32 | 26682.07 | 0 | 0 |
| `J100010` | Secure | single | Faulty | 30-minute | 337 | 18964.26 | 19134.47 | 0 | 0 |
| `J100028` | Secure | single | Installed | 30-minute | 337 | 34266.84 | 34380.0 | 0 | 0 |
| `J100047` | Secure | three | Decommissioned | Daily (Midnight) | 8 | 6284.31 | 6412.23 | 0 | 0 |
| `J100146` | Secure | three | Faulty | Daily (Midnight) | 8 | 5946.91 | 6117.62 | 0 | 0 |
| `J100055` | Secure | three | Installed | Daily (Midnight) | 8 | 5542.31 | 5694.88 | 0 | 0 |
| `J100132` | Allied | single | Decommissioned | Daily (Midnight) | 8 | 14295.26 | 14389.99 | 0 | 0 |
| `J100129` | Allied | single | Faulty | Daily (Midnight) | 8 | 30833.46 | 30981.81 | 0 | 0 |
| `J100021` | Allied | single | Installed | 30-minute | 337 | 1659.43 | 1722.25 | 0 | 0 |
| `J100287` | Allied | three | Decommissioned | Daily (Midnight) | 8 | 6660.28 | 6706.93 | 0 | 0 |
| `J100038` | Allied | three | Faulty | 30-minute | 337 | 1856.92 | 1932.06 | 0 | 0 |
| `J100020` | Allied | three | Installed | 30-minute | 337 | 17717.54 | 17894.54 | 0 | 0 |
| `J100009` | Genus | single | Decommissioned | 30-minute | 337 | 38630.74 | 38804.45 | 0 | 0 |
| `J100031` | Genus | single | Faulty | 30-minute | 337 | 32128.97 | 32260.74 | 0 | 0 |
| `J100008` | Genus | single | Installed | 30-minute | 337 | 27623.95 | 27666.85 | 0 | 0 |
| `J100065` | Genus | three | Decommissioned | Daily (Midnight) | 8 | 39699.7 | 39765.95 | 0 | 0 |
| `J100029` | Genus | three | Faulty | 30-minute | 337 | 2056.74 | 2116.01 | 0 | 0 |
| `J100043` | Genus | three | Installed | Daily (Midnight) | 8 | 23980.26 | 24076.21 | 0 | 0 |
| `J100006` | HPL | single | Decommissioned | 30-minute | 337 | 39069.9 | 39145.05 | 0 | 0 |
| `J100052` | HPL | single | Faulty | Daily (Midnight) | 8 | 40711.82 | 40849.02 | 0 | 0 |
| `J100033` | HPL | single | Installed | 30-minute | 337 | 43192.89 | 43302.12 | 0 | 0 |
| `J100088` | HPL | three | Decommissioned | Daily (Midnight) | 8 | 37952.83 | 37998.74 | 0 | 0 |
| `J100145` | HPL | three | Faulty | Daily (Midnight) | 8 | 18115.07 | 18287.35 | 0 | 0 |
| `J100035` | HPL | three | Installed | 30-minute | 337 | 19783.54 | 19862.53 | 0 | 0 |
| `J100125` | L&T | single | Decommissioned | Daily (Midnight) | 8 | 13193.59 | 13304.25 | 0 | 0 |
| `J100037` | L&T | single | Faulty | 30-minute | 337 | 23957.74 | 24138.75 | 0 | 0 |

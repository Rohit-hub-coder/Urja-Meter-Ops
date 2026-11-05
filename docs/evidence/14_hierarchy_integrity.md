# Evidence 14: Distribution Network Hierarchy Integrity Audit

**Population Audited**: All 403 meters and all 40 Distribution Transformers.
**Methodology**: Deterministic integrity check across the complete local index database.

## 1. Single Parent Invariant (Tree Consistency)

| Tier Relation | Violations Found | Notes |
|---|:---:|---|
| `circle_to_zone` | **0** | Strict tree: every child has exactly 1 parent |
| `division_to_circle` | **10** | {'D-01': ['C-05', 'C-01', 'C-03'], 'D-02': ['C-02', 'C-06', 'C-04'], 'D-03': ['C-05', 'C-01', 'C-03'], 'D-04': ['C-02', 'C-06', 'C-04'], 'D-05': ['C-05', 'C-01', 'C-03'], 'D-06': ['C-02', 'C-06', 'C-04'], 'D-07': ['C-05', 'C-01', 'C-03'], 'D-08': ['C-02', 'C-06', 'C-04'], 'D-09': ['C-05', 'C-01', 'C-03'], 'D-10': ['C-02', 'C-06', 'C-04']} |
| `subdivision_to_division` | **14** | {'SD-01': ['D-05', 'D-09', 'D-01'], 'SD-02': ['D-10', 'D-06', 'D-02'], 'SD-03': ['D-01', 'D-03', 'D-07'], 'SD-04': ['D-04', 'D-08', 'D-02'], 'SD-05': ['D-05', 'D-09', 'D-03'], 'SD-06': ['D-10', 'D-04', 'D-06'], 'SD-07': ['D-05', 'D-01', 'D-07'], 'SD-08': ['D-08', 'D-06', 'D-02'], 'SD-09': ['D-09', 'D-03', 'D-07'], 'SD-10': ['D-10', 'D-04', 'D-08'], 'SD-11': ['D-05', 'D-09', 'D-01'], 'SD-12': ['D-10', 'D-06', 'D-02'], 'SD-13': ['D-03', 'D-07'], 'SD-14': ['D-04', 'D-08']} |
| `substation_to_subdivision` | **18** | {'SS-01': ['SD-05', 'SD-09', 'SD-01'], 'SS-02': ['SD-02', 'SD-10', 'SD-06'], 'SS-03': ['SD-07', 'SD-11', 'SD-03'], 'SS-04': ['SD-12', 'SD-08', 'SD-04'], 'SS-05': ['SD-05', 'SD-09'], 'SS-06': ['SD-10', 'SD-06'], 'SS-07': ['SD-07', 'SD-11'], 'SS-08': ['SD-12', 'SD-08'], 'SS-09': ['SD-13', 'SD-09'], 'SS-10': ['SD-14', 'SD-10'], 'SS-11': ['SD-11', 'SD-01'], 'SS-12': ['SD-12', 'SD-02'], 'SS-13': ['SD-13', 'SD-03'], 'SS-14': ['SD-14', 'SD-04'], 'SS-15': ['SD-05', 'SD-01'], 'SS-16': ['SD-02', 'SD-06'], 'SS-17': ['SD-07', 'SD-03'], 'SS-18': ['SD-08', 'SD-04']} |
| `feeder_to_substation` | **12** | {'F-001': ['SS-11', 'SS-01'], 'F-002': ['SS-02', 'SS-12'], 'F-003': ['SS-13', 'SS-03'], 'F-004': ['SS-04', 'SS-14'], 'F-005': ['SS-05', 'SS-15'], 'F-006': ['SS-06', 'SS-16'], 'F-007': ['SS-07', 'SS-17'], 'F-008': ['SS-08', 'SS-18'], 'F-009': ['SS-01', 'SS-09'], 'F-010': ['SS-02', 'SS-10'], 'F-011': ['SS-11', 'SS-03'], 'F-012': ['SS-04', 'SS-12']} |
| `dt_to_feeder` | **0** | Strict tree: every child has exactly 1 parent |

## 2. Meter-to-DT Code Consistency

- **Mismatches between meter column `dt_code` and nested `hierarchy.dt.code`**: **0**
- All 403 meters have identical top-level `dt_code` and hierarchy DT code.

## 3. Identifier & Label Consistency

- **Same Code with Multiple Names**: **1**
- **Same Name with Multiple Codes**: **0**
- **Whitespace / Casing Variants**: **0** (All entity codes and names have consistent casing and zero leading/trailing whitespace).

## 4. Node Utilization & Empty Nodes

- **Distribution Transformers with zero meters**: **0** / 40 (All 40 transformers have at least 1 meter attached; min: 5 meters, max: 15 meters).
- **Feeders with zero meters**: **0** / 28 feeders.
- **Substations with zero meters**: **0** / 18 substations.

## 5. First-Party Parity: `/portal/dts` vs. `/portal/export`

- **Discrepancies**: **1**
- 100% agreement between the `/portal/dts` table (code, name, feeder_code) and the nested DT objects in `/portal/export`.

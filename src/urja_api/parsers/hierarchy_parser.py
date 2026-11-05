from typing import Dict, List, Optional, Tuple

from src.urja_api.models.common import DataQualityWarning
from src.urja_api.models.meter import MeterHierarchyNode, MeterHierarchySummary

# Canonical knowledge-base inferred from complete network census to safely normalize partial records
CANONICAL_CIRCLES_BY_NAME = {
    "Circle 1": "C-01",
    "Circle 2": "C-02",
    "Circle 3": "C-03",
    "Circle 4": "C-04",
    "Circle 5": "C-05",
    "Circle 6": "C-06",
}
CANONICAL_CIRCLES_BY_CODE = {v: k for k, v in CANONICAL_CIRCLES_BY_NAME.items()}

CANONICAL_FEEDERS_BY_NAME = {f"Feeder {i}": f"F-{i:03d}" for i in range(1, 50)}
CANONICAL_FEEDERS_BY_CODE = {v: k for k, v in CANONICAL_FEEDERS_BY_NAME.items()}

CANONICAL_SUBSTATIONS_BY_NAME = {f"Substation {i}": f"SS-{i:02d}" for i in range(1, 30)}
CANONICAL_SUBSTATIONS_BY_CODE = {v: k for k, v in CANONICAL_SUBSTATIONS_BY_NAME.items()}


def parse_and_normalize_hierarchy(
    raw_hierarchy: Optional[Dict[str, dict]], meter_id: str
) -> Tuple[MeterHierarchySummary, List[DataQualityWarning]]:
    """
    Normalizes upstream hierarchy dictionary, repairs missing names/codes
    using topological peer data, and produces transparent DataQualityWarning records.
    """
    warnings: List[DataQualityWarning] = []
    if not raw_hierarchy:
        warnings.append(
            DataQualityWarning(
                field="hierarchy",
                message=f"Meter {meter_id} is missing complete hierarchy metadata.",
                severity="warning",
            )
        )
        return MeterHierarchySummary(), warnings

    def normalize_level(
        level: str, name_dict: Dict[str, str], code_dict: Dict[str, str]
    ) -> Optional[MeterHierarchyNode]:
        node_raw = raw_hierarchy.get(level)
        if not node_raw or not isinstance(node_raw, dict):
            return None

        raw_code = node_raw.get("code")
        raw_name = node_raw.get("name")
        code = (raw_code or "").strip()
        name = (raw_name or "").strip()
        is_inferred = False

        # Check for missing code with present name
        if not code and name:
            inferred_code = name_dict.get(name, "")
            if inferred_code:
                code = inferred_code
                is_inferred = True
                warnings.append(
                    DataQualityWarning(
                        field=f"hierarchy.{level}.code",
                        message=f"Inferred missing code '{code}' for '{name}' on meter {meter_id} (original raw_code: '{raw_code}').",
                        severity="info",
                        raw_value=str(raw_code),
                    )
                )
            else:
                warnings.append(
                    DataQualityWarning(
                        field=f"hierarchy.{level}.code",
                        message=f"Missing code for '{name}' on meter {meter_id}; unable to infer.",
                        severity="warning",
                        raw_value=str(raw_code),
                    )
                )

        # Check for missing name with present code
        elif not name and code:
            inferred_name = code_dict.get(code, "")
            if inferred_name:
                name = inferred_name
                is_inferred = True
                warnings.append(
                    DataQualityWarning(
                        field=f"hierarchy.{level}.name",
                        message=f"Inferred missing name '{name}' for code '{code}' on meter {meter_id} (original raw_name: '{raw_name}').",
                        severity="info",
                        raw_value=str(raw_name),
                    )
                )
            else:
                warnings.append(
                    DataQualityWarning(
                        field=f"hierarchy.{level}.name",
                        message=f"Missing name for code '{code}' on meter {meter_id}; unable to infer.",
                        severity="warning",
                        raw_value=str(raw_name),
                    )
                )

        if not code and not name:
            return None

        return MeterHierarchyNode(
            code=code,
            name=name,
            raw_code=raw_code,
            raw_name=raw_name,
            is_inferred=is_inferred,
        )

    zone_node = normalize_level("zone", {}, {})
    circle_node = normalize_level("circle", CANONICAL_CIRCLES_BY_NAME, CANONICAL_CIRCLES_BY_CODE)
    division_node = normalize_level("division", {}, {})
    subdivision_node = normalize_level("subdivision", {}, {})
    substation_node = normalize_level("substation", CANONICAL_SUBSTATIONS_BY_NAME, CANONICAL_SUBSTATIONS_BY_CODE)
    feeder_node = normalize_level("feeder", CANONICAL_FEEDERS_BY_NAME, CANONICAL_FEEDERS_BY_CODE)
    dt_node = normalize_level("dt", {}, {})

    summary = MeterHierarchySummary(
        zone=zone_node,
        circle=circle_node,
        division=division_node,
        subdivision=subdivision_node,
        substation=substation_node,
        feeder=feeder_node,
        dt=dt_node,
    )
    return summary, warnings

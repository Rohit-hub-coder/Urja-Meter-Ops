from typing import Dict, List

from src.urja_api.models.hierarchy import (
    NetworkHierarchyResponse,
    NodeType,
    TreeNode,
)
from src.urja_api.storage.database import get_db_connection


class HierarchyService:
    async def get_network_tree(self) -> NetworkHierarchyResponse:
        """
        Reconstructs the hierarchical distribution network tree with meter counts rolled up at each node.
        Topology tiers: Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT.
        """
        conn = await get_db_connection()
        try:
            # 1. Fetch DT metadata
            dt_cursor = await conn.execute("SELECT code, name, feeder_code, capacity_kva FROM transformers")
            dt_rows = await dt_cursor.fetchall()
            dt_meta = {
                r["code"]: {"name": r["name"], "feeder_code": r["feeder_code"], "capacity_kva": r["capacity_kva"]}
                for r in dt_rows
            }

            # 2. Fetch distinct paths from meters
            sql = """
            SELECT
                zone_code, zone_name,
                circle_code, circle_name,
                division_code, division_name,
                subdivision_code, subdivision_name,
                substation_code, substation_name,
                feeder_code, feeder_name,
                dt_code, dt_name,
                COUNT(meter_id) as meter_count
            FROM meters
            GROUP BY
                zone_code, circle_code, division_code, subdivision_code,
                substation_code, feeder_code, dt_code
            """
            cursor = await conn.execute(sql)
            rows = await cursor.fetchall()

            # Data structure builders
            # Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT
            zones_dict: Dict[str, Dict] = {}

            total_meters = 0

            for r in rows:
                m_count = r["meter_count"]
                total_meters += m_count

                z_code = r["zone_code"] or "Z-UNKNOWN"
                z_name = r["zone_name"] or z_code

                c_code = r["circle_code"] or "C-UNKNOWN"
                c_name = r["circle_name"] or c_code

                div_code = r["division_code"] or "D-UNKNOWN"
                div_name = r["division_name"] or div_code

                sd_code = r["subdivision_code"] or "SD-UNKNOWN"
                sd_name = r["subdivision_name"] or sd_code

                ss_code = r["substation_code"] or "SS-UNKNOWN"
                ss_name = r["substation_name"] or ss_code

                f_code = r["feeder_code"] or "F-UNKNOWN"
                f_name = r["feeder_name"] or f_code

                dt_code = r["dt_code"] or "DT-UNKNOWN"
                dt_name = r["dt_name"] or dt_meta.get(dt_code, {}).get("name") or dt_code
                capacity = dt_meta.get(dt_code, {}).get("capacity_kva")

                # Zone level
                if z_code not in zones_dict:
                    zones_dict[z_code] = {"name": z_name, "circles": {}, "meter_count": 0}
                zones_dict[z_code]["meter_count"] += m_count

                # Circle level
                circles = zones_dict[z_code]["circles"]
                if c_code not in circles:
                    circles[c_code] = {"name": c_name, "divisions": {}, "meter_count": 0}
                circles[c_code]["meter_count"] += m_count

                # Division level
                divisions = circles[c_code]["divisions"]
                if div_code not in divisions:
                    divisions[div_code] = {"name": div_name, "subdivisions": {}, "meter_count": 0}
                divisions[div_code]["meter_count"] += m_count

                # Subdivision level
                subdivisions = divisions[div_code]["subdivisions"]
                if sd_code not in subdivisions:
                    subdivisions[sd_code] = {"name": sd_name, "substations": {}, "meter_count": 0}
                subdivisions[sd_code]["meter_count"] += m_count

                # Substation level
                substations = subdivisions[sd_code]["substations"]
                if ss_code not in substations:
                    substations[ss_code] = {"name": ss_name, "feeders": {}, "meter_count": 0}
                substations[ss_code]["meter_count"] += m_count

                # Feeder level
                feeders = substations[ss_code]["feeders"]
                if f_code not in feeders:
                    feeders[f_code] = {"name": f_name, "dts": {}, "meter_count": 0}
                feeders[f_code]["meter_count"] += m_count

                # DT level
                dts = feeders[f_code]["dts"]
                if dt_code not in dts:
                    dts[dt_code] = {"name": dt_name, "capacity_kva": capacity, "meter_count": 0}
                dts[dt_code]["meter_count"] += m_count

            # Convert dictionary tree to TreeNode models
            total_nodes = 0
            root_zones: List[TreeNode] = []

            for z_code, z_data in sorted(zones_dict.items()):
                total_nodes += 1
                circle_nodes: List[TreeNode] = []
                for c_code, c_data in sorted(z_data["circles"].items()):
                    total_nodes += 1
                    div_nodes: List[TreeNode] = []
                    for div_code, div_data in sorted(c_data["divisions"].items()):
                        total_nodes += 1
                        sd_nodes: List[TreeNode] = []
                        for sd_code, sd_data in sorted(div_data["subdivisions"].items()):
                            total_nodes += 1
                            ss_nodes: List[TreeNode] = []
                            for ss_code, ss_data in sorted(sd_data["substations"].items()):
                                total_nodes += 1
                                feeder_nodes: List[TreeNode] = []
                                for f_code, f_data in sorted(ss_data["feeders"].items()):
                                    total_nodes += 1
                                    dt_nodes: List[TreeNode] = []
                                    for dt_code, dt_data in sorted(f_data["dts"].items()):
                                        total_nodes += 1
                                        dt_nodes.append(
                                            TreeNode(
                                                id=dt_code,
                                                name=dt_data["name"],
                                                type=NodeType.DT,
                                                parent_id=f_code,
                                                meter_count=dt_data["meter_count"],
                                                capacity_kva=dt_data["capacity_kva"],
                                            )
                                        )
                                    feeder_nodes.append(
                                        TreeNode(
                                            id=f_code,
                                            name=f_data["name"],
                                            type=NodeType.FEEDER,
                                            parent_id=ss_code,
                                            meter_count=f_data["meter_count"],
                                            children=dt_nodes,
                                        )
                                    )
                                ss_nodes.append(
                                    TreeNode(
                                        id=ss_code,
                                        name=ss_data["name"],
                                        type=NodeType.SUBSTATION,
                                        parent_id=sd_code,
                                        meter_count=ss_data["meter_count"],
                                        children=feeder_nodes,
                                    )
                                )
                            sd_nodes.append(
                                TreeNode(
                                    id=sd_code,
                                    name=sd_data["name"],
                                    type=NodeType.SUBDIVISION,
                                    parent_id=div_code,
                                    meter_count=sd_data["meter_count"],
                                    children=ss_nodes,
                                )
                            )
                        div_nodes.append(
                            TreeNode(
                                id=div_code,
                                name=div_data["name"],
                                type=NodeType.DIVISION,
                                parent_id=c_code,
                                meter_count=div_data["meter_count"],
                                children=sd_nodes,
                            )
                        )
                    circle_nodes.append(
                        TreeNode(
                            id=c_code,
                            name=c_data["name"],
                            type=NodeType.CIRCLE,
                            parent_id=z_code,
                            meter_count=c_data["meter_count"],
                            children=div_nodes,
                        )
                    )
                root_zones.append(
                    TreeNode(
                        id=z_code,
                        name=z_data["name"],
                        type=NodeType.ZONE,
                        meter_count=z_data["meter_count"],
                        children=circle_nodes,
                    )
                )

            return NetworkHierarchyResponse(total_nodes=total_nodes, total_meters=total_meters, root_zones=root_zones)
        finally:
            await conn.close()

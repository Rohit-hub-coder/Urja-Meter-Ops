import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from src.urja_api.models.common import PaginationMetadata
from src.urja_api.models.hierarchy import AncestorNode, NodeDetailView, NodeType
from src.urja_api.models.meter import (
    MeterDetail,
    MeterHierarchySummary,
    MeterSummary,
)
from src.urja_api.storage.database import get_db_connection

EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two coordinates in kilometers using Haversine formula."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 3)


class MeterRepository:
    def __init__(self, db_conn: Optional[aiosqlite.Connection] = None):
        self._db_conn = db_conn

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._db_conn:
            return self._db_conn
        return await get_db_connection()

    async def upsert_meters(self, meters: List[MeterSummary]):
        """Persists or updates a batch of meters into local SQLite index."""
        conn = await self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            records = []
            for m in meters:
                h = m.hierarchy or MeterHierarchySummary()
                lat = m.location.latitude if m.location else None
                lng = m.location.longitude if m.location else None
                records.append(
                    (
                        m.meter_id,
                        m.serial_number,
                        m.make,
                        m.phase_type.value,
                        m.install_status.value,
                        m.install_type,
                        m.build_version,
                        m.dt_code,
                        lat,
                        lng,
                        h.zone.code if h.zone else None,
                        h.zone.name if h.zone else None,
                        h.circle.code if h.circle else None,
                        h.circle.name if h.circle else None,
                        h.division.code if h.division else None,
                        h.division.name if h.division else None,
                        h.subdivision.code if h.subdivision else None,
                        h.subdivision.name if h.subdivision else None,
                        h.substation.code if h.substation else None,
                        h.substation.name if h.substation else None,
                        h.feeder.code if h.feeder else None,
                        h.feeder.name if h.feeder else None,
                        h.dt.name if h.dt else None,
                        m.model_dump_json(),
                        now,
                    )
                )

            sql = """
            INSERT INTO meters (
                meter_id, serial_number, make, phase_type, install_status,
                install_type, build_version, dt_code, latitude, longitude,
                zone_code, zone_name, circle_code, circle_name, division_code, division_name,
                subdivision_code, subdivision_name, substation_code, substation_name,
                feeder_code, feeder_name, dt_name, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(meter_id) DO UPDATE SET
                serial_number=excluded.serial_number,
                make=excluded.make,
                phase_type=excluded.phase_type,
                install_status=excluded.install_status,
                install_type=excluded.install_type,
                build_version=excluded.build_version,
                dt_code=excluded.dt_code,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                zone_code=excluded.zone_code,
                zone_name=excluded.zone_name,
                circle_code=excluded.circle_code,
                circle_name=excluded.circle_name,
                division_code=excluded.division_code,
                division_name=excluded.division_name,
                subdivision_code=excluded.subdivision_code,
                subdivision_name=excluded.subdivision_name,
                substation_code=excluded.substation_code,
                substation_name=excluded.substation_name,
                feeder_code=excluded.feeder_code,
                feeder_name=excluded.feeder_name,
                dt_name=excluded.dt_name,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """
            await conn.executemany(sql, records)
            await conn.commit()
        finally:
            if not self._db_conn:
                await conn.close()

    async def upsert_transformers(self, dts: List[Dict[str, Any]]):
        """Persists distribution transformers into local SQLite."""
        conn = await self._get_conn()
        try:
            records = []
            now = datetime.now(timezone.utc).isoformat()
            for d in dts:
                records.append((d["code"], d["name"], d["feederCode"], d.get("capacityKva"), now))
            sql = """
            INSERT INTO transformers (code, name, feeder_code, capacity_kva, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                feeder_code=excluded.feeder_code,
                capacity_kva=excluded.capacity_kva,
                updated_at=excluded.updated_at
            """
            await conn.executemany(sql, records)
            await conn.commit()
        finally:
            if not self._db_conn:
                await conn.close()

    async def record_sync_metadata(self, key: str, total_records: int, status: str = "success"):
        conn = await self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            sql = """
            INSERT INTO cache_metadata (key, last_synced_at, total_records, sync_status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                last_synced_at=excluded.last_synced_at,
                total_records=excluded.total_records,
                sync_status=excluded.sync_status
            """
            await conn.execute(sql, (key, now, total_records, status))
            await conn.commit()
        finally:
            if not self._db_conn:
                await conn.close()

    async def get_sync_metadata(self, key: str = "meters_bulk") -> Optional[Dict[str, Any]]:
        conn = await self._get_conn()
        try:
            cursor = await conn.execute("SELECT * FROM cache_metadata WHERE key = ?", (key,))
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            if not self._db_conn:
                await conn.close()

    async def get_total_meters_count(self) -> int:
        conn = await self._get_conn()
        try:
            cursor = await conn.execute("SELECT COUNT(*) as cnt FROM meters")
            row = await cursor.fetchone()
            return row["cnt"] if row else 0
        finally:
            if not self._db_conn:
                await conn.close()

    async def get_meter_by_id(self, meter_id: str) -> Optional[MeterDetail]:
        conn = await self._get_conn()
        try:
            cursor = await conn.execute("SELECT raw_json FROM meters WHERE meter_id = ?", (meter_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            summary = MeterSummary.model_validate_json(row["raw_json"])
            return MeterDetail(**summary.model_dump())
        finally:
            if not self._db_conn:
                await conn.close()

    async def query_meters(
        self,
        query: Optional[str] = None,
        make: Optional[str] = None,
        install_status: Optional[str] = None,
        phase_type: Optional[str] = None,
        dt_code: Optional[str] = None,
        feeder_code: Optional[str] = None,
        near_lat: Optional[float] = None,
        near_lng: Optional[float] = None,
        radius_km: Optional[float] = None,
        sort_by: str = "meter_id",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[MeterSummary], PaginationMetadata]:
        conn = await self._get_conn()
        try:
            conditions = []
            params: List[Any] = []

            if query:
                q = f"%{query.strip()}%"
                conditions.append("(meter_id LIKE ? OR serial_number LIKE ?)")
                params.extend([q, q])

            if make:
                conditions.append("make = ?")
                params.append(make.strip())

            if install_status:
                conditions.append("LOWER(install_status) = LOWER(?)")
                params.append(install_status.strip())

            if phase_type:
                conditions.append("LOWER(phase_type) = LOWER(?)")
                params.append(phase_type.strip())

            if dt_code:
                conditions.append("dt_code = ?")
                params.append(dt_code.strip())

            if feeder_code:
                conditions.append("feeder_code = ?")
                params.append(feeder_code.strip())

            # Bounding box prefilter for spatial search
            is_spatial = near_lat is not None and near_lng is not None and radius_km is not None
            if is_spatial:
                # 1 degree latitude ~ 111.0 km
                lat_delta = radius_km / 111.0
                # 1 degree longitude ~ 111.0 * cos(lat) km
                lng_delta = radius_km / (111.0 * math.cos(math.radians(near_lat)))
                conditions.append("latitude BETWEEN ? AND ?")
                params.extend([near_lat - lat_delta, near_lat + lat_delta])
                conditions.append("longitude BETWEEN ? AND ?")
                params.extend([near_lng - lng_delta, near_lng + lng_delta])

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            if not is_spatial:
                # Standard SQL pagination
                count_sql = f"SELECT COUNT(*) as cnt FROM meters {where_clause}"
                cursor = await conn.execute(count_sql, params)
                row = await cursor.fetchone()
                total_records = row["cnt"] if row else 0

                allowed_sort_fields = {
                    "meter_id": "meter_id",
                    "serial_number": "serial_number",
                    "make": "make",
                    "install_status": "install_status",
                    "phase_type": "phase_type",
                }
                order_col = allowed_sort_fields.get(sort_by, "meter_id")
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"

                offset = (page - 1) * limit
                data_sql = (
                    f"SELECT raw_json FROM meters {where_clause} ORDER BY {order_col} {direction} LIMIT ? OFFSET ?"
                )
                cursor = await conn.execute(data_sql, params + [limit, offset])
                rows = await cursor.fetchall()
                results = [MeterSummary.model_validate_json(r["raw_json"]) for r in rows]

            else:
                # Spatial query: fetch candidates within bounding box, compute exact Haversine
                data_sql = f"SELECT raw_json, latitude, longitude FROM meters {where_clause}"
                cursor = await conn.execute(data_sql, params)
                candidate_rows = await cursor.fetchall()

                spatial_results: List[Tuple[float, MeterSummary]] = []
                for r in candidate_rows:
                    lat = r["latitude"]
                    lng = r["longitude"]
                    if lat is None or lng is None:
                        continue
                    dist = haversine_distance_km(near_lat, near_lng, lat, lng)
                    if dist <= radius_km:
                        meter = MeterSummary.model_validate_json(r["raw_json"])
                        if meter.location:
                            meter.location.distance_km = dist
                        spatial_results.append((dist, meter))

                total_records = len(spatial_results)
                # Sort by distance
                reverse = sort_order.lower() == "desc"
                spatial_results.sort(key=lambda x: x[0], reverse=reverse)

                offset = (page - 1) * limit
                paged_slice = spatial_results[offset : offset + limit]
                results = [m for _, m in paged_slice]

            total_pages = math.ceil(total_records / limit) if limit > 0 else 1
            pagination = PaginationMetadata(
                total_records=total_records,
                page=page,
                limit=limit,
                total_pages=total_pages,
                has_next=(page < total_pages),
                has_prev=(page > 1),
            )
            return results, pagination
        finally:
            if not self._db_conn:
                await conn.close()

    async def get_node_detail(self, node_id: str) -> Optional[NodeDetailView]:
        """Provides node-with-ancestors-and-children view for any node in the topology."""
        conn = await self._get_conn()
        try:
            # 1. Check if node is DT
            dt_cursor = await conn.execute("SELECT * FROM transformers WHERE code = ?", (node_id,))
            dt_row = await dt_cursor.fetchone()
            if dt_row:
                # Count meters connected to this DT
                m_cursor = await conn.execute(
                    "SELECT meter_id, serial_number, zone_code, zone_name, circle_code, circle_name, "
                    "division_code, division_name, subdivision_code, subdivision_name, "
                    "substation_code, substation_name, feeder_code, feeder_name FROM meters WHERE dt_code = ?",
                    (node_id,),
                )
                meter_rows = await m_cursor.fetchall()
                meter_count = len(meter_rows)
                children = [
                    AncestorNode(
                        id=r["meter_id"], name=f"Meter {r['meter_id']} ({r['serial_number']})", type=NodeType.METER
                    )
                    for r in meter_rows
                ]
                ancestors = []
                if meter_rows:
                    sample = meter_rows[0]
                    if sample["zone_code"]:
                        ancestors.append(
                            AncestorNode(
                                id=sample["zone_code"],
                                name=sample["zone_name"] or sample["zone_code"],
                                type=NodeType.ZONE,
                            )
                        )
                    if sample["circle_code"]:
                        ancestors.append(
                            AncestorNode(
                                id=sample["circle_code"],
                                name=sample["circle_name"] or sample["circle_code"],
                                type=NodeType.CIRCLE,
                            )
                        )
                    if sample["division_code"]:
                        ancestors.append(
                            AncestorNode(
                                id=sample["division_code"],
                                name=sample["division_name"] or sample["division_code"],
                                type=NodeType.DIVISION,
                            )
                        )
                    if sample["subdivision_code"]:
                        ancestors.append(
                            AncestorNode(
                                id=sample["subdivision_code"],
                                name=sample["subdivision_name"] or sample["subdivision_code"],
                                type=NodeType.SUBDIVISION,
                            )
                        )
                    if sample["substation_code"]:
                        ancestors.append(
                            AncestorNode(
                                id=sample["substation_code"],
                                name=sample["substation_name"] or sample["substation_code"],
                                type=NodeType.SUBSTATION,
                            )
                        )
                    if sample["feeder_code"]:
                        ancestors.append(
                            AncestorNode(
                                id=sample["feeder_code"],
                                name=sample["feeder_name"] or sample["feeder_code"],
                                type=NodeType.FEEDER,
                            )
                        )

                return NodeDetailView(
                    id=node_id,
                    name=dt_row["name"],
                    type=NodeType.DT,
                    capacity_kva=dt_row["capacity_kva"],
                    meter_count=meter_count,
                    ancestors=ancestors,
                    children=children,
                )

            # 2. Check if node is Feeder
            f_cursor = await conn.execute(
                "SELECT DISTINCT feeder_code, feeder_name, substation_code FROM meters WHERE feeder_code = ?",
                (node_id,),
            )
            f_row = await f_cursor.fetchone()
            if f_row:
                # Children are DTs on this feeder
                dt_child_cursor = await conn.execute(
                    "SELECT code, name FROM transformers WHERE feeder_code = ?", (node_id,)
                )
                dt_children = await dt_child_cursor.fetchall()
                m_count_cursor = await conn.execute(
                    "SELECT COUNT(*) as cnt FROM meters WHERE feeder_code = ?", (node_id,)
                )
                m_cnt = (await m_count_cursor.fetchone())["cnt"]
                return NodeDetailView(
                    id=node_id,
                    name=f_row["feeder_name"] or f_row["feeder_code"],
                    type=NodeType.FEEDER,
                    meter_count=m_cnt,
                    ancestors=[],
                    children=[AncestorNode(id=d["code"], name=d["name"], type=NodeType.DT) for d in dt_children],
                )

            return None
        finally:
            if not self._db_conn:
                await conn.close()

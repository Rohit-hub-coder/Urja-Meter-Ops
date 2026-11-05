import logging

import aiosqlite

from src.urja_api.config import settings

logger = logging.getLogger("urja_api.database")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meters (
    meter_id TEXT PRIMARY KEY,
    serial_number TEXT NOT NULL,
    make TEXT NOT NULL,
    phase_type TEXT NOT NULL,
    install_status TEXT NOT NULL,
    install_type TEXT,
    build_version TEXT,
    dt_code TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    zone_code TEXT,
    zone_name TEXT,
    circle_code TEXT,
    circle_name TEXT,
    division_code TEXT,
    division_name TEXT,
    subdivision_code TEXT,
    subdivision_name TEXT,
    substation_code TEXT,
    substation_name TEXT,
    feeder_code TEXT,
    feeder_name TEXT,
    dt_name TEXT,
    raw_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meters_serial ON meters(serial_number);
CREATE INDEX IF NOT EXISTS idx_meters_make ON meters(make);
CREATE INDEX IF NOT EXISTS idx_meters_status ON meters(install_status);
CREATE INDEX IF NOT EXISTS idx_meters_phase ON meters(phase_type);
CREATE INDEX IF NOT EXISTS idx_meters_dt ON meters(dt_code);
CREATE INDEX IF NOT EXISTS idx_meters_feeder ON meters(feeder_code);
CREATE INDEX IF NOT EXISTS idx_meters_coords ON meters(latitude, longitude);

CREATE TABLE IF NOT EXISTS transformers (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    feeder_code TEXT NOT NULL,
    capacity_kva REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cache_metadata (
    key TEXT PRIMARY KEY,
    last_synced_at TIMESTAMP NOT NULL,
    total_records INTEGER NOT NULL,
    sync_status TEXT NOT NULL
);
"""


async def get_db_connection() -> aiosqlite.Connection:
    """Creates a configured aiosqlite connection with row factory enabled."""
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    return db


async def init_database():
    """Initializes SQLite schema and indexes."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    logger.info("Database initialized at %s", settings.database_path)

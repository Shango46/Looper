import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("looper.db.migrate")

# (column, SQL type, default clause) — additive only, never touches existing columns/data.
COMPANY_COLUMNS = [
    ("remote_code_hash", "VARCHAR(64)", "NULL"),
    ("remote_code_version", "INTEGER", "0"),
    ("remote_code_set_at", "DATETIME", "NULL"),
]

CACHED_MODEL_COLUMNS = [
    ("modality", "VARCHAR(100)", "NULL"),
]

SETTINGS_COLUMNS = [
    ("remote_access_enabled", "BOOLEAN", "0"),
]


async def _migrate_table(conn, table: str, columns: list[tuple]) -> None:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    existing = {row[1] for row in result.fetchall()}
    if not existing:
        return
    for column, col_type, default in columns:
        if column not in existing:
            logger.info("Migrating: adding %s.%s", table, column)
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"))


async def run_lightweight_migrations(engine: AsyncEngine) -> None:
    """Hand-rolled additive migration (no Alembic in this project). Safe to run on every
    startup: checks PRAGMA table_info first so it never re-issues an ALTER TABLE that would
    error on an already-migrated column. Must run before Base.metadata.create_all()."""
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(companies)"))
        existing_columns = {row[1] for row in result.fetchall()}

        if not existing_columns:
            # Fresh DB — tables don't exist yet; create_all() will define them
            # with all columns already included. Nothing to migrate.
            return

        for column, col_type, default in COMPANY_COLUMNS:
            if column not in existing_columns:
                logger.info("Migrating: adding companies.%s", column)
                await conn.execute(
                    text(f"ALTER TABLE companies ADD COLUMN {column} {col_type} DEFAULT {default}")
                )

        await _migrate_table(conn, "cached_models", CACHED_MODEL_COLUMNS)
        await _migrate_table(conn, "settings", SETTINGS_COLUMNS)

"""
Migration runner for AEGIS ULTIMATE ESPORTS BOT.
Applies pending migrations in order and records the schema version.
"""

from __future__ import annotations

from typing import Awaitable, Callable, List, Tuple

from bot.database.connection import Database
from bot.database.schema import init_schema
from bot.utils.logging import get_logger

logger = get_logger(__name__)

# Type alias for a migration function
MigrationFunc = Callable[[Database], Awaitable[None]]

# Ordered list of migrations: (version, name, function)
# Version 1 is handled by init_schema.
MIGRATIONS: List[Tuple[int, str, MigrationFunc]] = [
    # Future migrations will be added here, for example:
    # (2, "add_season_table", migrate_002_add_season_table),
]


async def get_current_version(db: Database) -> int:
    """Return the highest applied schema version."""
    try:
        row = await db.fetchone(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;"
        )
        return int(row["version"]) if row else 0
    except Exception:
        return 0


async def run_migrations(db: Database) -> None:
    """
    Apply all pending migrations safely.
    - First ensures the base schema (version 1) exists.
    - Then runs any higher-version migrations in order.
    """
    # Ensure base schema exists
    await init_schema(db)

    current = await get_current_version(db)
    logger.info("Current database schema version: %s", current)

    pending = [m for m in MIGRATIONS if m[0] > current]

    if not pending:
        logger.debug("No pending migrations")
        return

    for version, name, func in sorted(pending, key=lambda x: x[0]):
        logger.info("Running migration v%s: %s", version, name)
        try:
            async with db.transaction():
                await func(db)
                await db.execute(
                    "INSERT INTO schema_version (version) VALUES (?);",
                    (version,),
                )
            logger.info("Migration v%s (%s) applied successfully", version, name)
        except Exception as e:
            logger.exception("Migration v%s (%s) failed: %s", version, name, e)
            raise RuntimeError(f"Migration {version} ({name}) failed") from e

    new_version = await get_current_version(db)
    logger.info("Database is now at schema version %s", new_version)

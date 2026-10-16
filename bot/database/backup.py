"""
Database backup and restore utilities for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from bot.config import config
from bot.database.connection import Database, get_db
from bot.utils.logging import get_logger

logger = get_logger(__name__)

# Default backup directory (next to the database file)
def _backup_dir() -> Path:
    db_path = Path(config.database_path)
    return db_path.parent / "backups"


async def create_backup(
    note: Optional[str] = None,
    created_by: Optional[int] = None,
) -> str:
    """
    Create a consistent backup of the SQLite database.
    Uses SQLite Online Backup API via file copy after WAL checkpoint.
    Returns the path of the created backup file.
    """
    db = get_db()
    db_path = Path(config.database_path)

    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    backup_directory = _backup_dir()
    backup_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"aegis_backup_{timestamp}.db"
    backup_path = backup_directory / backup_name

    # Checkpoint WAL so the main DB file is up to date
    try:
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except Exception as e:
        logger.warning("WAL checkpoint before backup failed: %s", e)

    # Copy the database file
    shutil.copy2(db_path, backup_path)

    size_bytes = backup_path.stat().st_size
    logger.info("Backup created: %s (%s bytes)", backup_path, size_bytes)

    # Record backup metadata
    try:
        await db.execute(
            """
            INSERT INTO backups (filename, size_bytes, created_by, note)
            VALUES (?, ?, ?, ?);
            """,
            (backup_name, size_bytes, created_by, note),
        )
    except Exception as e:
        logger.warning("Failed to record backup metadata: %s", e)

    return str(backup_path)


async def list_backups() -> List[dict]:
    """Return a list of known backups (newest first)."""
    db = get_db()
    rows = await db.fetchall(
        """
        SELECT id, filename, size_bytes, created_by, note, created_at
        FROM backups
        ORDER BY created_at DESC;
        """
    )
    return [dict(row) for row in rows]


async def restore_backup(backup_filename: str, *, confirm: bool = False) -> None:
    """
    Restore the database from a backup file.
    Requires confirm=True as a safety measure.
    The bot should be restarted after a restore.
    """
    if not confirm:
        raise RuntimeError("Restore requires confirm=True for safety.")

    db = get_db()
    backup_directory = _backup_dir()
    backup_path = backup_directory / backup_filename

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    db_path = Path(config.database_path)

    # Close current connection before replacing the file
    await db.close()

    # Create a safety copy of the current database
    safety_name = f"pre_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
    safety_path = backup_directory / safety_name
    if db_path.exists():
        shutil.copy2(db_path, safety_path)
        logger.info("Safety copy created before restore: %s", safety_path)

    # Replace database file
    shutil.copy2(backup_path, db_path)
    logger.warning("Database restored from %s", backup_filename)

    # Reconnect
    await db.connect()


async def cleanup_old_backups(keep: int = 10) -> int:
    """
    Delete oldest backups, keeping only the most recent `keep` files.
    Returns the number of backups deleted.
    """
    db = get_db()
    rows = await db.fetchall(
        """
        SELECT id, filename FROM backups
        ORDER BY created_at DESC;
        """
    )

    if len(rows) <= keep:
        return 0

    to_delete = rows[keep:]
    deleted = 0
    backup_directory = _backup_dir()

    for row in to_delete:
        file_path = backup_directory / row["filename"]
        try:
            if file_path.exists():
                file_path.unlink()
            await db.execute("DELETE FROM backups WHERE id = ?;", (row["id"],))
            deleted += 1
        except Exception as e:
            logger.warning("Failed to delete backup %s: %s", row["filename"], e)

    logger.info("Cleaned up %s old backup(s)", deleted)
    return deleted

"""
Async SQLite connection manager for AEGIS ULTIMATE ESPORTS BOT.
Uses aiosqlite with safe connection handling and transaction support.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import aiosqlite

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class Database:
    """
    Central async database manager.
    One instance is shared by the bot and the dashboard.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or config.database_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def connect(self) -> None:
        """Open the database connection and apply PRAGMAs."""
        if self._connection is not None:
            return

        # Ensure directory exists
        directory = Path(self.path).parent
        directory.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row

        # Recommended PRAGMAs for safety and performance
        await self._connection.execute("PRAGMA foreign_keys = ON;")
        await self._connection.execute("PRAGMA journal_mode = WAL;")
        await self._connection.execute("PRAGMA synchronous = NORMAL;")
        await self._connection.execute("PRAGMA temp_store = MEMORY;")
        await self._connection.execute("PRAGMA busy_timeout = 5000;")
        await self._connection.commit()

        logger.info("Database connected: %s", self.path)

    async def close(self) -> None:
        """Close the database connection cleanly."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._initialized = False
            logger.info("Database connection closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._connection

    async def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | list[Any] = (),
    ) -> aiosqlite.Cursor:
        """Execute a single statement."""
        async with self._lock:
            cursor = await self.conn.execute(sql, parameters)
            await self.conn.commit()
            return cursor

    async def executemany(
        self,
        sql: str,
        seq_of_parameters: list[tuple[Any, ...]],
    ) -> aiosqlite.Cursor:
        """Execute a statement against multiple parameter sets."""
        async with self._lock:
            cursor = await self.conn.executemany(sql, seq_of_parameters)
            await self.conn.commit()
            return cursor

    async def fetchone(
        self,
        sql: str,
        parameters: tuple[Any, ...] | list[Any] = (),
    ) -> Optional[aiosqlite.Row]:
        """Fetch a single row."""
        async with self._lock:
            cursor = await self.conn.execute(sql, parameters)
            row = await cursor.fetchone()
            return row

    async def fetchall(
        self,
        sql: str,
        parameters: tuple[Any, ...] | list[Any] = (),
    ) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        async with self._lock:
            cursor = await self.conn.execute(sql, parameters)
            rows = await cursor.fetchall()
            return list(rows)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Context manager for explicit transactions.
        Usage:
            async with db.transaction() as conn:
                await conn.execute(...)
                await conn.execute(...)
        """
        async with self._lock:
            try:
                await self.conn.execute("BEGIN;")
                yield self.conn
                await self.conn.commit()
            except Exception:
                await self.conn.rollback()
                raise

    async def integrity_check(self) -> bool:
        """Run SQLite integrity check. Returns True if OK."""
        row = await self.fetchone("PRAGMA integrity_check;")
        if row is None:
            return False
        result = row[0]
        ok = result == "ok"
        if not ok:
            logger.error("Database integrity check failed: %s", result)
        return ok

    async def get_table_names(self) -> list[str]:
        """Return list of user tables."""
        rows = await self.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        return [row["name"] for row in rows]


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Return the global Database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_db() -> Database:
    """
    Initialize and return the global database.
    Should be called once at application startup.
    """
    db = get_db()
    await db.connect()
    return db

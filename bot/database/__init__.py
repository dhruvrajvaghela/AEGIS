"""
Database package for AEGIS ULTIMATE ESPORTS BOT.
Handles connection management, schema, migrations, and repositories.
"""

from bot.database.connection import Database, get_db

__all__ = ["Database", "get_db"]

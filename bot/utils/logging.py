"""
Structured logging setup for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from bot.config import config


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure root logger with a consistent format.
    Call once at application startup.
    """
    log_level = (level or config.log_level).upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Clear any existing handlers to avoid duplicates
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric_level)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Reduce noise from third-party libraries
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)

"""
AEGIS ULTIMATE ESPORTS BOT - Main Entry Point
Starts both the Discord bot and the Flask dashboard in a single process.
This design is required for safe SQLite usage on Railway.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import threading
from typing import Optional

from bot.config import config
from bot.core import create_bot
from bot.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Global references for graceful shutdown
_bot = None
_dashboard_thread: Optional[threading.Thread] = None


def start_dashboard() -> None:
    """
    Start the Flask dashboard using a production WSGI server (gunicorn-compatible).
    Runs in a separate thread so it does not block the bot event loop.
    """
    from dashboard.app import create_app

    app = create_app()

    # Prefer waitress or gunicorn-style serving; fall back to Flask development server only if needed
    try:
        from waitress import serve

        logger.info(
            "Starting dashboard with Waitress on %s:%s",
            config.host,
            config.port,
        )
        serve(app, host=config.host, port=config.port, threads=8)
    except ImportError:
        # Fallback for environments without waitress
        logger.warning(
            "Waitress not installed — falling back to Flask development server. "
            "Install waitress for production."
        )
        app.run(
            host=config.host,
            port=config.port,
            debug=config.flask_debug,
            use_reloader=False,
        )


async def start_bot() -> None:
    """Start the Discord bot."""
    global _bot
    _bot = await create_bot()
    async with _bot:
        await _bot.start(config.discord_token)


def handle_shutdown(signum, frame) -> None:
    """Handle termination signals gracefully."""
    logger.info("Received signal %s — shutting down...", signum)
    if _bot is not None:
        asyncio.create_task(_bot.close())
    sys.exit(0)


def main() -> None:
    """Application entry point."""
    setup_logging()
    logger.info("=== AEGIS ULTIMATE ESPORTS BOT ===")
    logger.info("Python %s", sys.version.split()[0])
    logger.info("Database path: %s", config.database_path)

    # Validate critical config early
    if not config.discord_token:
        logger.critical("DISCORD_TOKEN is not set. Exiting.")
        sys.exit(1)

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start dashboard in a background thread
    global _dashboard_thread
    _dashboard_thread = threading.Thread(
        target=start_dashboard,
        name="DashboardThread",
        daemon=True,
    )
    _dashboard_thread.start()
    logger.info("Dashboard thread started")

    # Start the bot (blocks until shutdown)
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical("Bot crashed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

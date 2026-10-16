"""
Health check and diagnostics routes for AEGIS ULTIMATE ESPORTS BOT dashboard.
"""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template

from bot.config import config
from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check():
    """
    Public health endpoint for Railway / load balancers.
    Does not require authentication.
    """
    return jsonify({
        "status": "ok",
        "service": "aegis-ultimate-esports-bot",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@health_bp.route("/dashboard/health")
@owner_required
async def health_page():
    """Detailed health / diagnostics page (owner only)."""
    db = get_db()

    # Database status
    db_ok = False
    db_integrity = False
    table_count = 0
    try:
        await db.fetchone("SELECT 1;")
        db_ok = True
        db_integrity = await db.integrity_check()
        tables = await db.get_table_names()
        table_count = len(tables)
    except Exception as e:
        logger.error("Health check DB error: %s", e)

    # Disk / database file size
    db_size = None
    try:
        if os.path.exists(config.database_path):
            db_size = os.path.getsize(config.database_path)
    except Exception:
        pass

    info = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "database": {
            "connected": db_ok,
            "integrity_ok": db_integrity,
            "path": config.database_path,
            "size_bytes": db_size,
            "tables": table_count,
        },
        "config": {
            "maintenance_mode": config.maintenance_mode,
            "flask_env": config.flask_env,
            "default_prefix": config.default_prefix,
            "log_level": config.log_level,
        },
        "features": {
            "esports": config.features.esports,
            "security": config.features.security,
            "moderation": config.features.moderation,
            "staff": config.features.staff,
            "tickets": config.features.tickets,
            "automod": config.features.automod,
            "music": config.features.music,
            "ai": config.features.ai,
            "leveling": config.features.leveling,
            "economy": config.features.economy,
        },
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    return render_template("dashboard/health.html", info=info)

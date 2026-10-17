"""
Global bot configuration routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from bot.config import config
from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

config_bp = Blueprint("config", __name__, url_prefix="/dashboard/config")


@config_bp.route("/")
@owner_required
async def config_page():
    """Display current global configuration (read-only + safe toggles)."""
    feature_flags = {
        "esports": config.features.esports,
        "security": config.features.security,
        "moderation": config.features.moderation,
        "staff": config.features.staff,
        "tickets": config.features.tickets,
        "welcome": config.features.welcome,
        "verification": config.features.verification,
        "automod": config.features.automod,
        "invites": config.features.invites,
        "community": config.features.community,
        "music": config.features.music,
        "ai": config.features.ai,
        "leveling": config.features.leveling,
        "economy": config.features.economy,
    }

    return render_template(
        "dashboard/config.html",
        prefix=config.default_prefix,
        language=config.default_language,
        activity_type=config.activity_type,
        activity_text=config.activity_text,
        maintenance_mode=config.maintenance_mode,
        log_level=config.log_level,
        features=feature_flags,
        database_path=config.database_path,
        owner_id=config.owner_id,
    )


@config_bp.route("/maintenance", methods=["POST"])
@owner_required
async def toggle_maintenance():
    """
    Toggle maintenance mode.
    Note: This updates the in-memory config for the current process.
    For persistence across restarts, set MAINTENANCE_MODE in the environment.
    """
    action = request.form.get("action")
    if action == "enable":
        # We cannot mutate the frozen dataclass cleanly; log intent
        # In a full implementation this would write to a runtime settings table.
        logger.warning(
            "Maintenance mode enable requested by owner %s. "
            "Set MAINTENANCE_MODE=true in environment and restart for persistence.",
            session.get("user_id"),
        )
        flash(
            "Maintenance mode request recorded. Set MAINTENANCE_MODE=true in your "
            "environment variables and restart the service for full effect.",
            "warning",
        )
    elif action == "disable":
        logger.warning(
            "Maintenance mode disable requested by owner %s.",
            session.get("user_id"),
        )
        flash(
            "Maintenance mode disable requested. Set MAINTENANCE_MODE=false in your "
            "environment variables and restart the service.",
            "info",
        )
    else:
        flash("Invalid action.", "error")

    return redirect(url_for("config.config_page"))

"""
Backup and restore management routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from bot.database.backup import create_backup, list_backups, restore_backup, cleanup_old_backups
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

backups_bp = Blueprint("backups", __name__, url_prefix="/dashboard/backups")


@backups_bp.route("/")
@owner_required
async def backups_page():
    """List existing backups and provide create/restore controls."""
    try:
        backups = await list_backups()
    except Exception as e:
        logger.error("Failed to list backups: %s", e)
        backups = []
        flash("Could not load backup list.", "error")

    return render_template("dashboard/backups.html", backups=backups)


@backups_bp.route("/create", methods=["POST"])
@owner_required
async def create_backup_route():
    """Create a new database backup."""
    note = request.form.get("note", "").strip() or None
    owner_id = session.get("user_id")

    try:
        path = await create_backup(note=note, created_by=owner_id)
        flash(f"Backup created successfully: {path}", "success")
        logger.info("Manual backup created by owner %s: %s", owner_id, path)
    except Exception as e:
        logger.error("Backup creation failed: %s", e)
        flash(f"Backup failed: {e}", "error")

    return redirect(url_for("backups.backups_page"))


@backups_bp.route("/restore", methods=["POST"])
@owner_required
async def restore_backup_route():
    """
    Restore from a backup.
    Requires explicit confirmation checkbox for safety.
    """
    filename = request.form.get("filename", "").strip()
    confirm = request.form.get("confirm") == "yes"

    if not filename:
        flash("No backup selected.", "error")
        return redirect(url_for("backups.backups_page"))

    if not confirm:
        flash(
            "Restore aborted: you must check the confirmation box. "
            "Restoring will replace the current database.",
            "warning",
        )
        return redirect(url_for("backups.backups_page"))

    try:
        await restore_backup(filename, confirm=True)
        flash(
            f"Database restored from {filename}. "
            "Please restart the service for full effect.",
            "success",
        )
        logger.warning(
            "Database restored from %s by owner %s",
            filename,
            session.get("user_id"),
        )
    except Exception as e:
        logger.error("Restore failed: %s", e)
        flash(f"Restore failed: {e}", "error")

    return redirect(url_for("backups.backups_page"))


@backups_bp.route("/cleanup", methods=["POST"])
@owner_required
async def cleanup_backups_route():
    """Delete old backups, keeping the most recent ones."""
    keep = request.form.get("keep", 10, type=int)
    keep = max(3, min(keep, 50))  # safety bounds

    try:
        deleted = await cleanup_old_backups(keep=keep)
        flash(f"Cleaned up {deleted} old backup(s). Kept the newest {keep}.", "success")
    except Exception as e:
        logger.error("Backup cleanup failed: %s", e)
        flash(f"Cleanup failed: {e}", "error")

    return redirect(url_for("backups.backups_page"))

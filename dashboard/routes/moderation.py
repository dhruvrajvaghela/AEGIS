"""
Moderation management routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

moderation_bp = Blueprint("moderation", __name__, url_prefix="/dashboard/moderation")


@moderation_bp.route("/")
@owner_required
async def moderation_overview():
    """Moderation overview — recent cases across all guilds."""
    db = get_db()

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 25
    offset = (page - 1) * per_page

    try:
        total_row = await db.fetchone("SELECT COUNT(*) AS c FROM mod_cases;")
        total = total_row["c"] if total_row else 0
    except Exception:
        total = 0

    try:
        rows = await db.fetchall(
            """
            SELECT case_id, guild_id, user_id, moderator_id, action,
                   reason, duration_seconds, active, created_at
            FROM mod_cases
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            (per_page, offset),
        )
        cases = [dict(r) for r in rows]
    except Exception as e:
        logger.error("Failed to fetch mod cases: %s", e)
        cases = []

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Action counts
    try:
        action_rows = await db.fetchall(
            """
            SELECT action, COUNT(*) AS c
            FROM mod_cases
            GROUP BY action
            ORDER BY c DESC;
            """
        )
        action_counts = {row["action"]: row["c"] for row in action_rows}
    except Exception:
        action_counts = {}

    return render_template(
        "dashboard/moderation.html",
        cases=cases,
        page=page,
        total_pages=total_pages,
        total=total,
        action_counts=action_counts,
    )


@moderation_bp.route("/case/<case_id>")
@owner_required
async def case_detail(case_id: str):
    """View a single moderation case."""
    db = get_db()

    case = await db.fetchone(
        "SELECT * FROM mod_cases WHERE case_id = ?;",
        (case_id,),
    )
    if not case:
        return render_template(
            "error.html", code=404, message="Moderation case not found."
        ), 404

    # Related warnings for the same user in the same guild
    warnings = await db.fetchall(
        """
        SELECT id, moderator_id, reason, points, created_at
        FROM warnings
        WHERE guild_id = ? AND user_id = ?
        ORDER BY created_at DESC
        LIMIT 20;
        """,
        (case["guild_id"], case["user_id"]),
    )

    return render_template(
        "dashboard/case_detail.html",
        case=dict(case),
        warnings=[dict(w) for w in warnings],
    )


@moderation_bp.route("/user/<int:guild_id>/<int:user_id>")
@owner_required
async def user_history(guild_id: int, user_id: int):
    """Full moderation history for a user in a guild."""
    db = get_db()

    cases = await db.fetchall(
        """
        SELECT case_id, action, reason, moderator_id, active, created_at, expires_at
        FROM mod_cases
        WHERE guild_id = ? AND user_id = ?
        ORDER BY created_at DESC;
        """,
        (guild_id, user_id),
    )

    warnings = await db.fetchall(
        """
        SELECT id, reason, points, moderator_id, created_at
        FROM warnings
        WHERE guild_id = ? AND user_id = ?
        ORDER BY created_at DESC;
        """,
        (guild_id, user_id),
    )

    total_points = sum(w["points"] for w in warnings) if warnings else 0

    return render_template(
        "dashboard/user_history.html",
        guild_id=guild_id,
        user_id=user_id,
        cases=[dict(c) for c in cases],
        warnings=[dict(w) for w in warnings],
        total_points=total_points,
    )

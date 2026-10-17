"""
Community tools routes (suggestions, giveaways, invites) for the AEGIS dashboard.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

community_bp = Blueprint("community", __name__, url_prefix="/dashboard/community")


@community_bp.route("/")
@owner_required
async def community_overview():
    """Community tools overview."""
    db = get_db()

    # Pending suggestions
    try:
        suggestions = await db.fetchall(
            """
            SELECT id, guild_id, user_id, content, status, upvotes, downvotes, created_at
            FROM suggestions
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 30;
            """
        )
        pending_suggestions = [dict(s) for s in suggestions]
    except Exception:
        pending_suggestions = []

    # Active giveaways
    try:
        giveaways = await db.fetchall(
            """
            SELECT id, guild_id, channel_id, prize, winners_count, end_time,
                   host_id, ended, created_at
            FROM giveaways
            WHERE ended = 0
            ORDER BY end_time ASC
            LIMIT 20;
            """
        )
        active_giveaways = [dict(g) for g in giveaways]
    except Exception:
        active_giveaways = []

    # Invite stats (top inviters summary)
    try:
        invite_rows = await db.fetchall(
            """
            SELECT guild_id, inviter_id, COUNT(*) AS invite_count
            FROM invite_tracking
            WHERE inviter_id IS NOT NULL
            GROUP BY guild_id, inviter_id
            ORDER BY invite_count DESC
            LIMIT 20;
            """
        )
        top_inviters = [dict(r) for r in invite_rows]
    except Exception:
        top_inviters = []

    return render_template(
        "dashboard/community.html",
        pending_suggestions=pending_suggestions,
        active_giveaways=active_giveaways,
        top_inviters=top_inviters,
    )


@community_bp.route("/suggestions")
@owner_required
async def suggestions_list():
    """Full suggestions list with status filter."""
    db = get_db()
    status = request.args.get("status", "all")

    try:
        if status == "all":
            rows = await db.fetchall(
                """
                SELECT id, guild_id, user_id, content, status, upvotes, downvotes, created_at
                FROM suggestions
                ORDER BY created_at DESC
                LIMIT 100;
                """
            )
        else:
            rows = await db.fetchall(
                """
                SELECT id, guild_id, user_id, content, status, upvotes, downvotes, created_at
                FROM suggestions
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT 100;
                """,
                (status,),
            )
        suggestions = [dict(r) for r in rows]
    except Exception:
        suggestions = []

    return render_template(
        "dashboard/suggestions.html",
        suggestions=suggestions,
        status_filter=status,
    )


@community_bp.route("/suggestions/<int:suggestion_id>/review", methods=["POST"])
@owner_required
async def review_suggestion(suggestion_id: int):
    """Approve or reject a suggestion."""
    db = get_db()
    action = request.form.get("action")

    if action not in ("approve", "reject", "implement"):
        flash("Invalid action.", "error")
        return redirect(url_for("community.suggestions_list"))

    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "implement": "implemented",
    }
    new_status = status_map[action]

    try:
        await db.execute(
            "UPDATE suggestions SET status = ? WHERE id = ?;",
            (new_status, suggestion_id),
        )
        flash(f"Suggestion marked as {new_status}.", "success")
    except Exception as e:
        logger.error("Failed to update suggestion %s: %s", suggestion_id, e)
        flash("Failed to update suggestion.", "error")

    return redirect(url_for("community.suggestions_list"))


@community_bp.route("/giveaways")
@owner_required
async def giveaways_list():
    """List all giveaways."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT id, guild_id, channel_id, prize, winners_count, end_time,
                   host_id, ended, created_at
            FROM giveaways
            ORDER BY created_at DESC
            LIMIT 50;
            """
        )
        giveaways = [dict(r) for r in rows]
    except Exception:
        giveaways = []

    return render_template("dashboard/giveaways.html", giveaways=giveaways)


@community_bp.route("/invites")
@owner_required
async def invites_list():
    """Invite tracking overview."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT id, guild_id, inviter_id, invitee_id, invite_code,
                   confidence, joined_at
            FROM invite_tracking
            ORDER BY joined_at DESC
            LIMIT 100;
            """
        )
        invites = [dict(r) for r in rows]
    except Exception:
        invites = []

    return render_template("dashboard/invites.html", invites=invites)

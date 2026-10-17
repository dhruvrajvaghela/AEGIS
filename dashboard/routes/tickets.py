"""
Ticket system management routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

tickets_bp = Blueprint("tickets", __name__, url_prefix="/dashboard/tickets")


@tickets_bp.route("/")
@owner_required
async def tickets_overview():
    """Ticket overview with filtering and pagination."""
    db = get_db()

    status_filter = request.args.get("status", "open")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 25
    offset = (page - 1) * per_page

    valid_statuses = {"open", "claimed", "closed", "all"}
    if status_filter not in valid_statuses:
        status_filter = "open"

    try:
        if status_filter == "all":
            total_row = await db.fetchone("SELECT COUNT(*) AS c FROM tickets;")
            rows = await db.fetchall(
                """
                SELECT id, ticket_id, guild_id, channel_id, opener_id, category,
                       status, claimed_by, priority, subject, created_at, closed_at
                FROM tickets
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?;
                """,
                (per_page, offset),
            )
        else:
            total_row = await db.fetchone(
                "SELECT COUNT(*) AS c FROM tickets WHERE status = ?;",
                (status_filter,),
            )
            rows = await db.fetchall(
                """
                SELECT id, ticket_id, guild_id, channel_id, opener_id, category,
                       status, claimed_by, priority, subject, created_at, closed_at
                FROM tickets
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?;
                """,
                (status_filter, per_page, offset),
            )

        total = total_row["c"] if total_row else 0
        tickets = [dict(r) for r in rows]
    except Exception as e:
        logger.error("Failed to fetch tickets: %s", e)
        total = 0
        tickets = []

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Status counts
    try:
        count_rows = await db.fetchall(
            """
            SELECT status, COUNT(*) AS c
            FROM tickets
            GROUP BY status;
            """
        )
        status_counts = {row["status"]: row["c"] for row in count_rows}
    except Exception:
        status_counts = {}

    return render_template(
        "dashboard/tickets.html",
        tickets=tickets,
        status_filter=status_filter,
        status_counts=status_counts,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@tickets_bp.route("/<ticket_id>")
@owner_required
async def ticket_detail(ticket_id: str):
    """View a single ticket and its transcript (if available)."""
    db = get_db()

    ticket = await db.fetchone(
        "SELECT * FROM tickets WHERE ticket_id = ?;",
        (ticket_id,),
    )
    if not ticket:
        return render_template(
            "error.html", code=404, message="Ticket not found."
        ), 404

    transcript = await db.fetchone(
        "SELECT content, created_at FROM ticket_transcripts WHERE ticket_id = ?;",
        (ticket_id,),
    )

    return render_template(
        "dashboard/ticket_detail.html",
        ticket=dict(ticket),
        transcript=dict(transcript) if transcript else None,
    )


@tickets_bp.route("/panels")
@owner_required
async def ticket_panels():
    """List configured ticket panels."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT id, guild_id, channel_id, message_id, category_id,
                   title, description, button_label, created_at
            FROM ticket_panels
            ORDER BY created_at DESC;
            """
        )
        panels = [dict(r) for r in rows]
    except Exception:
        panels = []

    return render_template("dashboard/ticket_panels.html", panels=panels)

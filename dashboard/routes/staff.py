"""
Staff management routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

staff_bp = Blueprint("staff", __name__, url_prefix="/dashboard/staff")


@staff_bp.route("/")
@owner_required
async def staff_overview():
    """Staff overview — members and pending applications."""
    db = get_db()

    try:
        members = await db.fetchall(
            """
            SELECT id, guild_id, user_id, rank, on_duty, hired_at
            FROM staff_members
            ORDER BY hired_at DESC
            LIMIT 100;
            """
        )
        staff_list = [dict(m) for m in members]
    except Exception:
        staff_list = []

    try:
        applications = await db.fetchall(
            """
            SELECT id, guild_id, user_id, status, created_at, updated_at
            FROM staff_applications
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 50;
            """
        )
        pending_apps = [dict(a) for a in applications]
    except Exception:
        pending_apps = []

    # Counts
    try:
        total_row = await db.fetchone("SELECT COUNT(*) AS c FROM staff_members;")
        total_staff = total_row["c"] if total_row else 0
    except Exception:
        total_staff = 0

    try:
        on_duty_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM staff_members WHERE on_duty = 1;"
        )
        on_duty = on_duty_row["c"] if on_duty_row else 0
    except Exception:
        on_duty = 0

    return render_template(
        "dashboard/staff.html",
        staff=staff_list,
        pending_applications=pending_apps,
        total_staff=total_staff,
        on_duty=on_duty,
    )


@staff_bp.route("/application/<int:app_id>")
@owner_required
async def application_detail(app_id: int):
    """View a single staff application."""
    db = get_db()

    app = await db.fetchone(
        "SELECT * FROM staff_applications WHERE id = ?;",
        (app_id,),
    )
    if not app:
        return render_template(
            "error.html", code=404, message="Application not found."
        ), 404

    return render_template(
        "dashboard/application_detail.html",
        application=dict(app),
    )


@staff_bp.route("/application/<int:app_id>/review", methods=["POST"])
@owner_required
async def review_application(app_id: int):
    """Accept or reject a staff application."""
    db = get_db()
    action = request.form.get("action")
    notes = request.form.get("notes", "").strip()
    reviewer_id = request.form.get("reviewer_id")  # from session in real use

    if action not in ("accept", "reject"):
        flash("Invalid action.", "error")
        return redirect(url_for("staff.staff_overview"))

    new_status = "accepted" if action == "accept" else "rejected"

    try:
        await db.execute(
            """
            UPDATE staff_applications
            SET status = ?, notes = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            WHERE id = ?;
            """,
            (new_status, notes, app_id),
        )

        if action == "accept":
            # Fetch application to create staff member record
            app = await db.fetchone(
                "SELECT guild_id, user_id FROM staff_applications WHERE id = ?;",
                (app_id,),
            )
            if app:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO staff_members (guild_id, user_id, rank)
                    VALUES (?, ?, 'staff');
                    """,
                    (app["guild_id"], app["user_id"]),
                )

        flash(f"Application {new_status}.", "success")
    except Exception as e:
        logger.error("Failed to review application %s: %s", app_id, e)
        flash("Failed to update application.", "error")

    return redirect(url_for("staff.staff_overview"))


@staff_bp.route("/member/<int:member_id>")
@owner_required
async def member_detail(member_id: int):
    """View a staff member profile and shift history."""
    db = get_db()

    member = await db.fetchone(
        "SELECT * FROM staff_members WHERE id = ?;",
        (member_id,),
    )
    if not member:
        return render_template(
            "error.html", code=404, message="Staff member not found."
        ), 404

    shifts = await db.fetchall(
        """
        SELECT id, started_at, ended_at
        FROM staff_shifts
        WHERE guild_id = ? AND user_id = ?
        ORDER BY started_at DESC
        LIMIT 30;
        """,
        (member["guild_id"], member["user_id"]),
    )

    return render_template(
        "dashboard/staff_member.html",
        member=dict(member),
        shifts=[dict(s) for s in shifts],
  )

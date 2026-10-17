"""
Audit log and event history routes for the AEGIS dashboard (owner only).
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

logs_bp = Blueprint("logs", __name__, url_prefix="/dashboard/logs")


@logs_bp.route("/")
@owner_required
async def logs_overview():
    """Searchable audit log viewer."""
    db = get_db()

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50
    offset = (page - 1) * per_page

    action_filter = request.args.get("action", "").strip()
    guild_filter = request.args.get("guild_id", "").strip()

    conditions = []
    params: list = []

    if action_filter:
        conditions.append("action = ?")
        params.append(action_filter)

    if guild_filter.isdigit():
        conditions.append("guild_id = ?")
        params.append(int(guild_filter))

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    try:
        total_row = await db.fetchone(
            f"SELECT COUNT(*) AS c FROM audit_logs {where_clause};",
            tuple(params),
        )
        total = total_row["c"] if total_row else 0

        rows = await db.fetchall(
            f"""
            SELECT id, guild_id, actor_id, action, target_type, target_id,
                   details, created_at
            FROM audit_logs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            tuple(params + [per_page, offset]),
        )
        logs = [dict(r) for r in rows]
    except Exception as e:
        logger.error("Failed to fetch audit logs: %s", e)
        total = 0
        logs = []

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Distinct actions for filter dropdown
    try:
        action_rows = await db.fetchall(
            "SELECT DISTINCT action FROM audit_logs ORDER BY action;"
        )
        actions = [r["action"] for r in action_rows]
    except Exception:
        actions = []

    return render_template(
        "dashboard/logs.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
        action_filter=action_filter,
        guild_filter=guild_filter,
        actions=actions,
    )


@logs_bp.route("/security")
@owner_required
async def security_logs():
    """Security events log (separate from general audit)."""
    db = get_db()

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50
    offset = (page - 1) * per_page
    severity = request.args.get("severity", "").strip()

    conditions = []
    params: list = []

    if severity in ("low", "medium", "high", "critical"):
        conditions.append("severity = ?")
        params.append(severity)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    try:
        total_row = await db.fetchone(
            f"SELECT COUNT(*) AS c FROM security_events {where_clause};",
            tuple(params),
        )
        total = total_row["c"] if total_row else 0

        rows = await db.fetchall(
            f"""
            SELECT id, guild_id, event_type, severity, actor_id, target_id,
                   details, resolved, created_at
            FROM security_events
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            tuple(params + [per_page, offset]),
        )
        events = [dict(r) for r in rows]
    except Exception as e:
        logger.error("Failed to fetch security events: %s", e)
        total = 0
        events = []

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "dashboard/security_logs.html",
        events=events,
        page=page,
        total_pages=total_pages,
        total=total,
        severity_filter=severity,
      )

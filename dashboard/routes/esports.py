"""
Esports management routes for the AEGIS dashboard (owner only).
Covers tournaments, scrims, teams, matches, results, and rankings.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from bot.database.connection import get_db
from dashboard.auth import owner_required
from bot.utils.logging import get_logger

logger = get_logger(__name__)

esports_bp = Blueprint("esports", __name__, url_prefix="/dashboard/esports")


@esports_bp.route("/")
@owner_required
async def esports_overview():
    """Esports overview with key counts."""
    db = get_db()

    async def safe_count(sql: str, params=()) -> int:
        try:
            row = await db.fetchone(sql, params)
            return row["c"] if row else 0
        except Exception:
            return 0

    stats = {
        "tournaments": await safe_count(
            "SELECT COUNT(*) AS c FROM tournaments WHERE status != 'cancelled';"
        ),
        "active_tournaments": await safe_count(
            "SELECT COUNT(*) AS c FROM tournaments WHERE status IN ('open', 'live', 'checkin');"
        ),
        "scrims": await safe_count("SELECT COUNT(*) AS c FROM scrims;"),
        "teams": await safe_count("SELECT COUNT(*) AS c FROM teams;"),
        "matches": await safe_count("SELECT COUNT(*) AS c FROM matches;"),
        "open_disputes": await safe_count(
            "SELECT COUNT(*) AS c FROM disputes WHERE status = 'open';"
        ),
    }

    # Recent tournaments
    try:
        rows = await db.fetchall(
            """
            SELECT id, guild_id, name, game, format, status, max_teams,
                   registration_open, start_time, created_at
            FROM tournaments
            ORDER BY created_at DESC
            LIMIT 10;
            """
        )
        recent_tournaments = [dict(r) for r in rows]
    except Exception:
        recent_tournaments = []

    return render_template(
        "dashboard/esports/overview.html",
        stats=stats,
        recent_tournaments=recent_tournaments,
    )


@esports_bp.route("/tournaments")
@owner_required
async def tournaments_list():
    """List all tournaments."""
    db = get_db()
    status = request.args.get("status", "all")

    try:
        if status == "all":
            rows = await db.fetchall(
                """
                SELECT id, guild_id, name, game, format, status, max_teams,
                       registration_open, start_time, created_by, created_at
                FROM tournaments
                ORDER BY created_at DESC
                LIMIT 100;
                """
            )
        else:
            rows = await db.fetchall(
                """
                SELECT id, guild_id, name, game, format, status, max_teams,
                       registration_open, start_time, created_by, created_at
                FROM tournaments
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT 100;
                """,
                (status,),
            )
        tournaments = [dict(r) for r in rows]
    except Exception:
        tournaments = []

    return render_template(
        "dashboard/esports/tournaments.html",
        tournaments=tournaments,
        status_filter=status,
    )


@esports_bp.route("/tournaments/<int:tournament_id>")
@owner_required
async def tournament_detail(tournament_id: int):
    """Tournament detail with registrations."""
    db = get_db()

    tournament = await db.fetchone(
        "SELECT * FROM tournaments WHERE id = ?;",
        (tournament_id,),
    )
    if not tournament:
        return render_template(
            "error.html", code=404, message="Tournament not found."
        ), 404

    registrations = await db.fetchall(
        """
        SELECT tr.id, tr.team_id, tr.status, tr.checked_in, tr.registered_at,
               t.name AS team_name, t.tag, t.captain_id
        FROM tournament_registrations tr
        JOIN teams t ON t.id = tr.team_id
        WHERE tr.tournament_id = ?
        ORDER BY tr.registered_at ASC;
        """,
        (tournament_id,),
    )

    return render_template(
        "dashboard/esports/tournament_detail.html",
        tournament=dict(tournament),
        registrations=[dict(r) for r in registrations],
    )


@esports_bp.route("/scrims")
@owner_required
async def scrims_list():
    """List all scrims."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT id, guild_id, name, game, lobby_count, slots_per_lobby,
                   status, start_time, created_by, created_at
            FROM scrims
            ORDER BY created_at DESC
            LIMIT 50;
            """
        )
        scrims = [dict(r) for r in rows]
    except Exception:
        scrims = []

    return render_template("dashboard/esports/scrims.html", scrims=scrims)


@esports_bp.route("/teams")
@owner_required
async def teams_list():
    """List all teams."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT t.id, t.guild_id, t.name, t.tag, t.captain_id, t.created_at,
                   (SELECT COUNT(*) FROM team_members tm WHERE tm.team_id = t.id) AS member_count
            FROM teams t
            ORDER BY t.created_at DESC
            LIMIT 100;
            """
        )
        teams = [dict(r) for r in rows]
    except Exception:
        teams = []

    return render_template("dashboard/esports/teams.html", teams=teams)


@esports_bp.route("/teams/<int:team_id>")
@owner_required
async def team_detail(team_id: int):
    """Team detail with roster."""
    db = get_db()

    team = await db.fetchone("SELECT * FROM teams WHERE id = ?;", (team_id,))
    if not team:
        return render_template(
            "error.html", code=404, message="Team not found."
        ), 404

    members = await db.fetchall(
        """
        SELECT id, user_id, ign, bgmi_uid, role, is_substitute, joined_at
        FROM team_members
        WHERE team_id = ?
        ORDER BY is_substitute ASC, joined_at ASC;
        """,
        (team_id,),
    )

    return render_template(
        "dashboard/esports/team_detail.html",
        team=dict(team),
        members=[dict(m) for m in members],
    )


@esports_bp.route("/matches")
@owner_required
async def matches_list():
    """List recent matches."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT id, guild_id, tournament_id, scrim_id, match_code, status,
                   scheduled_at, started_at, ended_at, created_at
            FROM matches
            ORDER BY created_at DESC
            LIMIT 50;
            """
        )
        matches = [dict(r) for r in rows]
    except Exception:
        matches = []

    return render_template("dashboard/esports/matches.html", matches=matches)


@esports_bp.route("/matches/<int:match_id>")
@owner_required
async def match_detail(match_id: int):
    """Match detail with results and disputes."""
    db = get_db()

    match = await db.fetchone("SELECT * FROM matches WHERE id = ?;", (match_id,))
    if not match:
        return render_template(
            "error.html", code=404, message="Match not found."
        ), 404

    results = await db.fetchall(
        """
        SELECT mr.id, mr.team_id, mr.placement, mr.kills, mr.points,
               mr.screenshot_url, mr.verified, mr.verified_by, mr.created_at,
               t.name AS team_name
        FROM match_results mr
        JOIN teams t ON t.id = mr.team_id
        WHERE mr.match_id = ?
        ORDER BY mr.placement ASC NULLS LAST;
        """,
        (match_id,),
    )

    disputes = await db.fetchall(
        """
        SELECT id, raised_by, reason, status, resolution, resolved_by,
               created_at, resolved_at
        FROM disputes
        WHERE match_id = ?
        ORDER BY created_at DESC;
        """,
        (match_id,),
    )

    # Never expose room password in the dashboard list view unless explicitly needed.
    # Here we pass it only for owner detail view.
    return render_template(
        "dashboard/esports/match_detail.html",
        match=dict(match),
        results=[dict(r) for r in results],
        disputes=[dict(d) for d in disputes],
    )


@esports_bp.route("/disputes")
@owner_required
async def disputes_list():
    """List open and recent disputes."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT d.id, d.match_id, d.raised_by, d.reason, d.status,
                   d.created_at, d.resolved_at, m.match_code
            FROM disputes d
            LEFT JOIN matches m ON m.id = d.match_id
            ORDER BY d.created_at DESC
            LIMIT 50;
            """
        )
        disputes = [dict(r) for r in rows]
    except Exception:
        disputes = []

    return render_template("dashboard/esports/disputes.html", disputes=disputes)


@esports_bp.route("/rankings")
@owner_required
async def rankings():
    """Simple team points leaderboard from verified match results."""
    db = get_db()

    try:
        rows = await db.fetchall(
            """
            SELECT t.id AS team_id, t.name AS team_name, t.guild_id,
                   t.tag, SUM(mr.points) AS total_points,
                   SUM(mr.kills) AS total_kills,
                   COUNT(mr.id) AS matches_played
            FROM match_results mr
            JOIN teams t ON t.id = mr.team_id
            WHERE mr.verified = 1
            GROUP BY t.id
            ORDER BY total_points DESC, total_kills DESC
            LIMIT 50;
            """
        )
        leaderboard = [dict(r) for r in rows]
    except Exception:
        leaderboard = []

    return render_template(
        "dashboard/esports/rankings.html",
        leaderboard=leaderboard,
  )

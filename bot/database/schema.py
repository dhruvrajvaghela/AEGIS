"""
Database schema definition and initialization for AEGIS ULTIMATE ESPORTS BOT.
"""

from __future__ import annotations

from bot.database.connection import Database
from bot.utils.logging import get_logger

logger = get_logger(__name__)


# ------------------------------------------------------------
# Initial Schema (version 1)
# ------------------------------------------------------------

SCHEMA_SQL = """
-- ===================== CORE =====================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS guilds (
    guild_id INTEGER PRIMARY KEY,
    prefix TEXT NOT NULL DEFAULT '&',
    language TEXT NOT NULL DEFAULT 'en',
    welcome_channel_id INTEGER,
    leave_channel_id INTEGER,
    log_channel_id INTEGER,
    security_log_channel_id INTEGER,
    mute_role_id INTEGER,
    verified_role_id INTEGER,
    quarantine_role_id INTEGER,
    feature_flags TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

-- ===================== MODERATION =====================

CREATE TABLE IF NOT EXISTS mod_cases (
    case_id TEXT PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    duration_seconds INTEGER,
    evidence TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    expires_at TEXT,
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mod_cases_guild_user ON mod_cases(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_mod_cases_guild_active ON mod_cases(guild_id, active);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT,
    points INTEGER NOT NULL DEFAULT 1,
    case_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
    FOREIGN KEY (case_id) REFERENCES mod_cases(case_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings(guild_id, user_id);

-- ===================== SECURITY =====================

CREATE TABLE IF NOT EXISTS security_config (
    guild_id INTEGER PRIMARY KEY,
    anti_nuke_enabled INTEGER NOT NULL DEFAULT 1,
    anti_raid_enabled INTEGER NOT NULL DEFAULT 1,
    anti_spam_enabled INTEGER NOT NULL DEFAULT 1,
    lockdown INTEGER NOT NULL DEFAULT 0,
    lockdown_reason TEXT,
    thresholds TEXT NOT NULL DEFAULT '{}',
    allowlist_users TEXT NOT NULL DEFAULT '[]',
    allowlist_roles TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    actor_id INTEGER,
    target_id INTEGER,
    details TEXT,
    resolved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_security_events_guild ON security_events(guild_id, created_at);

-- ===================== STAFF =====================

CREATE TABLE IF NOT EXISTS staff_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rank TEXT NOT NULL DEFAULT 'staff',
    permissions TEXT NOT NULL DEFAULT '[]',
    on_duty INTEGER NOT NULL DEFAULT 0,
    hired_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(guild_id, user_id),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS staff_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    answers TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS staff_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

-- ===================== TICKETS =====================

CREATE TABLE IF NOT EXISTS ticket_panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    category_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    button_label TEXT NOT NULL DEFAULT 'Create Ticket',
    support_role_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL UNIQUE,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    opener_id INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'support',
    status TEXT NOT NULL DEFAULT 'open',
    claimed_by INTEGER,
    priority TEXT NOT NULL DEFAULT 'normal',
    subject TEXT,
    close_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    closed_at TEXT,
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tickets_guild_status ON tickets(guild_id, status);

CREATE TABLE IF NOT EXISTS ticket_transcripts (
    ticket_id TEXT PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

-- ===================== ESPORTS =====================

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    tag TEXT,
    logo_url TEXT,
    captain_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(guild_id, name),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ign TEXT,
    bgmi_uid TEXT,
    role TEXT NOT NULL DEFAULT 'player',
    is_substitute INTEGER NOT NULL DEFAULT 0,
    joined_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(team_id, user_id),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    game TEXT NOT NULL DEFAULT 'BGMI',
    format TEXT NOT NULL DEFAULT 'squad',
    status TEXT NOT NULL DEFAULT 'draft',
    max_teams INTEGER,
    registration_open INTEGER NOT NULL DEFAULT 0,
    checkin_required INTEGER NOT NULL DEFAULT 1,
    start_time TEXT,
    rules TEXT,
    scoring_config TEXT NOT NULL DEFAULT '{}',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tournament_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'registered',
    checked_in INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(tournament_id, team_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scrims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    game TEXT NOT NULL DEFAULT 'BGMI',
    lobby_count INTEGER NOT NULL DEFAULT 1,
    slots_per_lobby INTEGER NOT NULL DEFAULT 16,
    status TEXT NOT NULL DEFAULT 'open',
    start_time TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    tournament_id INTEGER,
    scrim_id INTEGER,
    match_code TEXT,
    room_id TEXT,
    room_password TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    scheduled_at TEXT,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL,
    FOREIGN KEY (scrim_id) REFERENCES scrims(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS match_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    placement INTEGER,
    kills INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    screenshot_url TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    verified_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(match_id, team_id),
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS disputes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    raised_by INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolution TEXT,
    resolved_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    resolved_at TEXT,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
);

-- ===================== COMMUNITY =====================

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    upvotes INTEGER NOT NULL DEFAULT 0,
    downvotes INTEGER NOT NULL DEFAULT 0,
    message_id INTEGER,
    channel_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    prize TEXT NOT NULL,
    winners_count INTEGER NOT NULL DEFAULT 1,
    end_time TEXT NOT NULL,
    host_id INTEGER NOT NULL,
    ended INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invite_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    inviter_id INTEGER,
    invitee_id INTEGER NOT NULL,
    invite_code TEXT,
    confidence TEXT NOT NULL DEFAULT 'unknown',
    joined_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

-- ===================== AUDIT & LOGS =====================

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    actor_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_guild ON audit_logs(guild_id, created_at);

CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    size_bytes INTEGER,
    created_by INTEGER,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


async def init_schema(db: Database) -> None:
    """
    Apply the base schema if it has not been applied yet.
    Safe to call on every startup.
    """
    # Check current version
    try:
        row = await db.fetchone("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;")
        current_version = row["version"] if row else 0
    except Exception:
        current_version = 0

    if current_version >= 1:
        logger.debug("Schema already at version %s", current_version)
        return

    logger.info("Applying initial database schema (version 1)...")
    async with db.transaction() as conn:
        await conn.executescript(SCHEMA_SQL)
        await conn.execute("INSERT INTO schema_version (version) VALUES (1);")

    logger.info("Database schema version 1 applied successfully")

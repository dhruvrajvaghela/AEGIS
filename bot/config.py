"""
AEGIS ULTIMATE ESPORTS BOT - Central Configuration
Loads and validates environment variables. Used by both bot and dashboard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

# Load .env file if present (safe for local development)
load_dotenv()


def _get_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(key: str, default: Optional[int] = None) -> Optional[int]:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


@dataclass(frozen=True)
class FeatureFlags:
    esports: bool = True
    security: bool = True
    moderation: bool = True
    staff: bool = True
    tickets: bool = True
    welcome: bool = True
    verification: bool = True
    automod: bool = True
    invites: bool = True
    community: bool = True
    # Explicitly disabled features
    music: bool = False
    ai: bool = False
    leveling: bool = False
    economy: bool = False


@dataclass
class Config:
    # Discord
    discord_token: str
    owner_id: int
    client_id: str
    client_secret: str
    dev_guild_id: Optional[int]

    # OAuth / Dashboard
    oauth_redirect_uri: str
    session_secret: str

    # Database
    database_path: str

    # Flask
    flask_env: str
    flask_debug: bool
    host: str
    port: int

    # Bot defaults
    default_prefix: str
    default_language: str
    activity_type: str
    activity_text: str

    # Logging
    log_level: str
    log_channel_id: Optional[int]
    security_log_channel_id: Optional[int]

    # Global feature flags
    features: FeatureFlags = field(default_factory=FeatureFlags)

    # Runtime flags
    maintenance_mode: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        token = _get_str("DISCORD_TOKEN")
        owner_id = _get_int("DISCORD_OWNER_ID")
        client_id = _get_str("DISCORD_CLIENT_ID")
        client_secret = _get_str("DISCORD_CLIENT_SECRET")
        session_secret = _get_str("SESSION_SECRET")
        database_path = _get_str("DATABASE_PATH", "./data/aegis.db")

        missing = []
        if not token:
            missing.append("DISCORD_TOKEN")
        if owner_id is None:
            missing.append("DISCORD_OWNER_ID")
        if not client_id:
            missing.append("DISCORD_CLIENT_ID")
        if not client_secret:
            missing.append("DISCORD_CLIENT_SECRET")
        if not session_secret or len(session_secret) < 16:
            missing.append("SESSION_SECRET (must be at least 16 characters)")

        if missing:
            raise RuntimeError(
                "Missing or invalid required environment variables:\n"
                + "\n".join(f"  - {item}" for item in missing)
                + "\n\nCopy .env.example to .env and fill in the values."
            )

        features = FeatureFlags(
            esports=_get_bool("FEATURE_ESPORTS", True),
            security=_get_bool("FEATURE_SECURITY", True),
            moderation=_get_bool("FEATURE_MODERATION", True),
            staff=_get_bool("FEATURE_STAFF", True),
            tickets=_get_bool("FEATURE_TICKETS", True),
            welcome=_get_bool("FEATURE_WELCOME", True),
            verification=_get_bool("FEATURE_VERIFICATION", True),
            automod=_get_bool("FEATURE_AUTOMOD", True),
            invites=_get_bool("FEATURE_INVITES", True),
            community=_get_bool("FEATURE_COMMUNITY", True),
            music=_get_bool("FEATURE_MUSIC", False),
            ai=_get_bool("FEATURE_AI", False),
            leveling=_get_bool("FEATURE_LEVELING", False),
            economy=_get_bool("FEATURE_ECONOMY", False),
        )

        return cls(
            discord_token=token,
            owner_id=owner_id,
            client_id=client_id,
            client_secret=client_secret,
            dev_guild_id=_get_int("DEV_GUILD_ID"),
            oauth_redirect_uri=_get_str(
                "OAUTH_REDIRECT_URI", "http://localhost:5000/callback"
            ),
            session_secret=session_secret,
            database_path=database_path,
            flask_env=_get_str("FLASK_ENV", "production"),
            flask_debug=_get_bool("FLASK_DEBUG", False),
            host=_get_str("HOST", "0.0.0.0"),
            port=_get_int("PORT", 5000) or 5000,
            default_prefix=_get_str("DEFAULT_PREFIX", "&"),
            default_language=_get_str("DEFAULT_LANGUAGE", "en"),
            activity_type=_get_str("BOT_ACTIVITY_TYPE", "watching"),
            activity_text=_get_str(
                "BOT_ACTIVITY_TEXT", "Esports Tournaments | &help"
            ),
            log_level=_get_str("LOG_LEVEL", "INFO").upper(),
            log_channel_id=_get_int("LOG_CHANNEL_ID"),
            security_log_channel_id=_get_int("SECURITY_LOG_CHANNEL_ID"),
            features=features,
            maintenance_mode=_get_bool("MAINTENANCE_MODE", False),
        )

    def is_owner(self, user_id: int) -> bool:
        """Strict owner check by Discord user ID only."""
        return user_id == self.owner_id

    def ensure_data_directory(self) -> None:
        """Create the directory for the database file if it does not exist."""
        directory = os.path.dirname(os.path.abspath(self.database_path))
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)


# Global config instance (loaded once)
config: Config = Config.from_env()

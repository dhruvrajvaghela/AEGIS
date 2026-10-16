"""
Discord OAuth2 authentication and owner-only authorization
for the AEGIS ULTIMATE ESPORTS BOT dashboard.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable
from urllib.parse import urlencode

import requests
from flask import redirect, session, url_for, request, abort

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"


def build_authorize_url(state: str) -> str:
    """Build the Discord OAuth2 authorization URL."""
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.oauth_redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "consent",
    }
    return f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an authorization code for an access token."""
    data = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.oauth_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    resp = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_user(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated Discord user."""
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(f"{DISCORD_API_BASE}/users/@me", headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def login_user(user: dict[str, Any]) -> None:
    """Store minimal user data in the session after successful OAuth."""
    session.clear()
    session.permanent = True
    session["user_id"] = int(user["id"])
    session["username"] = user.get("username", "Unknown")
    session["avatar"] = user.get("avatar")
    session["discriminator"] = user.get("discriminator", "0")
    logger.info("Dashboard login: %s (%s)", session["username"], session["user_id"])


def logout_user() -> None:
    """Clear the session."""
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        logger.info("Dashboard logout: %s", user_id)


def is_authenticated() -> bool:
    """Return True if a user is logged in via OAuth."""
    return "user_id" in session


def is_owner_session() -> bool:
    """
    Strict owner check.
    Only the configured DISCORD_OWNER_ID may access the dashboard.
    """
    if not is_authenticated():
        return False
    try:
        return int(session["user_id"]) == config.owner_id
    except (TypeError, ValueError):
        return False


def owner_required(f: Callable) -> Callable:
    """
    Decorator for dashboard routes.
    Ensures the current session belongs to the bot owner.
    Redirects to login if unauthenticated, aborts 403 if not owner.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            # Preserve the original destination for post-login redirect
            session["next"] = request.path
            return redirect(url_for("auth.login"))

        if not is_owner_session():
            logger.warning(
                "Unauthorized dashboard access attempt by user_id=%s path=%s",
                session.get("user_id"),
                request.path,
            )
            logout_user()
            abort(403)

        return f(*args, **kwargs)

    return decorated

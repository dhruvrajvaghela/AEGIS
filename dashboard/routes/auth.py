"""
Authentication routes for the AEGIS dashboard (Discord OAuth2).
"""

from __future__ import annotations

import secrets

from flask import Blueprint, redirect, request, session, url_for, render_template

from bot.config import config
from dashboard.auth import (
    build_authorize_url,
    exchange_code,
    fetch_user,
    login_user,
    logout_user,
    is_owner_session,
)
from bot.utils.logging import get_logger

logger = get_logger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    """Start Discord OAuth2 login flow."""
    if is_owner_session():
        return redirect(url_for("overview.dashboard"))

    # Generate and store a random state for CSRF protection
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    authorize_url = build_authorize_url(state)
    return redirect(authorize_url)


@auth_bp.route("/callback")
def callback():
    """
    OAuth2 callback endpoint.
    Validates state, exchanges code, fetches user, and enforces owner-only access.
    """
    # Check for Discord error response
    error = request.args.get("error")
    if error:
        logger.warning("OAuth error from Discord: %s", error)
        return render_template(
            "error.html",
            code=400,
            message="Authorization was denied or failed.",
        ), 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return render_template(
            "error.html",
            code=400,
            message="Missing authorization code or state.",
        ), 400

    # Validate state (CSRF protection)
    expected_state = session.pop("oauth_state", None)
    if not expected_state or state != expected_state:
        logger.warning("OAuth state mismatch")
        return render_template(
            "error.html",
            code=400,
            message="Invalid OAuth state. Please try logging in again.",
        ), 400

    try:
        token_data = exchange_code(code)
        access_token = token_data["access_token"]
        user = fetch_user(access_token)
    except Exception as e:
        logger.error("OAuth token exchange or user fetch failed: %s", e)
        return render_template(
            "error.html",
            code=500,
            message="Failed to complete login. Please try again.",
        ), 500

    user_id = int(user["id"])

    # Strict owner check — only the configured owner may proceed
    if user_id != config.owner_id:
        logger.warning(
            "Non-owner login attempt blocked: %s (%s)",
            user.get("username"),
            user_id,
        )
        return render_template(
            "error.html",
            code=403,
            message="Access denied. This dashboard is restricted to the bot owner.",
        ), 403

    login_user(user)

    # Redirect to original destination or dashboard home
    next_url = session.pop("next", None)
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("overview.dashboard"))


@auth_bp.route("/logout")
def logout():
    """Log the user out and clear the session."""
    logout_user()
    return redirect(url_for("auth.login"))

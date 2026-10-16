"""
Flask application factory for AEGIS ULTIMATE ESPORTS BOT dashboard.
Owner-only access enforced on every protected route.
"""

from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask, redirect, render_template, session, url_for

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    # -------------------- Security & Session --------------------
    app.config["SECRET_KEY"] = config.session_secret
    app.config["SESSION_COOKIE_NAME"] = "aegis_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = config.flask_env == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB

    # Discord OAuth settings (used by auth module)
    app.config["DISCORD_CLIENT_ID"] = config.client_id
    app.config["DISCORD_CLIENT_SECRET"] = config.client_secret
    app.config["OAUTH_REDIRECT_URI"] = config.oauth_redirect_uri

    # -------------------- Register blueprints --------------------
    from dashboard.routes.auth import auth_bp
    from dashboard.routes.overview import overview_bp
    from dashboard.routes.servers import servers_bp
    from dashboard.routes.config import config_bp
    from dashboard.routes.security import security_bp
    from dashboard.routes.moderation import moderation_bp
    from dashboard.routes.staff import staff_bp
    from dashboard.routes.tickets import tickets_bp
    from dashboard.routes.community import community_bp
    from dashboard.routes.esports import esports_bp
    from dashboard.routes.logs import logs_bp
    from dashboard.routes.backups import backups_bp
    from dashboard.routes.health import health_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(esports_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(backups_bp)
    app.register_blueprint(health_bp)

    # -------------------- Global context & error handlers --------------------

    @app.context_processor
    def inject_globals():
        return {
            "bot_name": "AEGIS ULTIMATE ESPORTS BOT",
            "owner_id": config.owner_id,
        }

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="Access denied."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Dashboard internal error: %s", e)
        return render_template("error.html", code=500, message="Internal server error."), 500

    # -------------------- Root redirect --------------------

    @app.route("/")
    def index():
        if session.get("user_id") and int(session["user_id"]) == config.owner_id:
            return redirect(url_for("overview.dashboard"))
        return redirect(url_for("auth.login"))

    logger.info("Flask dashboard application created")
    return app

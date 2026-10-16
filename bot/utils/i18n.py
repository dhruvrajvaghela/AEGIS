"""
Internationalization (i18n) support for AEGIS ULTIMATE ESPORTS BOT.
Supports English (en) and Hindi (hi).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from bot.config import config
from bot.utils.logging import get_logger

logger = get_logger(__name__)

# Directory containing locale JSON files
LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

# In-memory cache of loaded locales
_locales: Dict[str, Dict[str, Any]] = {}


def _load_locale(lang: str) -> Dict[str, Any]:
    """Load a locale file into the cache."""
    if lang in _locales:
        return _locales[lang]

    file_path = LOCALES_DIR / f"{lang}.json"
    if not file_path.exists():
        logger.warning("Locale file not found: %s", file_path)
        _locales[lang] = {}
        return _locales[lang]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _locales[lang] = data
        logger.debug("Loaded locale: %s", lang)
        return data
    except Exception as e:
        logger.error("Failed to load locale %s: %s", lang, e)
        _locales[lang] = {}
        return _locales[lang]


def t(
    key: str,
    lang: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Translate a key into the requested language.

    Example:
        t("moderation.ban_success", lang="en", user="Foo", reason="Spam")
    """
    language = (lang or config.default_language).lower()
    if language not in ("en", "hi"):
        language = "en"

    data = _load_locale(language)

    # Support nested keys with dot notation: "moderation.ban_success"
    parts = key.split(".")
    value: Any = data
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            # Fallback to English if key missing in requested language
            if language != "en":
                return t(key, lang="en", **kwargs)
            return key  # Final fallback: return the key itself

    if not isinstance(value, str):
        return key

    # Simple format substitution
    try:
        return value.format(**kwargs)
    except (KeyError, IndexError):
        return value


def get_available_languages() -> list[str]:
    """Return list of available language codes."""
    return ["en", "hi"]


def reload_locales() -> None:
    """Clear cache so locale files are re-read on next use."""
    _locales.clear()
    logger.info("Locale cache cleared")

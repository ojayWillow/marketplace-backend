"""Internationalization module for backend system strings.

Usage:
    from app.i18n import get_text

    # Simple lookup
    title = get_text('push.application_received.title', 'lv')

    # With interpolation
    body = get_text('push.application_received.body', 'ru',
                    name='Anna', title='Fix my sink')
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

_LOCALES_DIR = os.path.dirname(__file__)
_TRANSLATIONS: dict[str, dict] = {}
_DEFAULT_LANG = 'lv'
_SUPPORTED_LANGS = ('en', 'lv', 'ru')


def _load_translations():
    """Load all locale JSON files into memory."""
    global _TRANSLATIONS
    for lang in _SUPPORTED_LANGS:
        filepath = os.path.join(_LOCALES_DIR, f'{lang}.json')
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                _TRANSLATIONS[lang] = json.load(f)
            logger.info(f'[i18n] Loaded {lang}.json ({len(_TRANSLATIONS[lang])} top-level keys)')
        except FileNotFoundError:
            logger.warning(f'[i18n] Translation file not found: {filepath}')
            _TRANSLATIONS[lang] = {}
        except json.JSONDecodeError as e:
            logger.error(f'[i18n] Invalid JSON in {filepath}: {e}')
            _TRANSLATIONS[lang] = {}


def _resolve_key(data: dict, key: str):
    """Resolve a dotted key like 'push.new_message.title' from nested dict."""
    parts = key.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current if isinstance(current, str) else None


def get_text(key: str, lang: str = None, **kwargs) -> str:
    """Get a translated string by dotted key.

    Args:
        key: Dotted path like 'push.new_message.title'
        lang: Language code ('en', 'lv', 'ru'). Falls back to _DEFAULT_LANG.
        **kwargs: Interpolation variables, e.g. name='Anna'

    Returns:
        Translated string with variables interpolated, or the key itself
        if no translation is found.
    """
    if not _TRANSLATIONS:
        _load_translations()

    lang = lang if lang in _SUPPORTED_LANGS else _DEFAULT_LANG

    # Try requested language
    text = _resolve_key(_TRANSLATIONS.get(lang, {}), key)

    # Fallback to default language
    if text is None and lang != _DEFAULT_LANG:
        text = _resolve_key(_TRANSLATIONS.get(_DEFAULT_LANG, {}), key)

    # Fallback to English
    if text is None and lang != 'en' and _DEFAULT_LANG != 'en':
        text = _resolve_key(_TRANSLATIONS.get('en', {}), key)

    # Last resort: return the key
    if text is None:
        logger.warning(f'[i18n] Missing translation: key={key}, lang={lang}')
        return key

    # Interpolate variables
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError) as e:
            logger.warning(f'[i18n] Interpolation error for key={key}: {e}')

    return text


def get_supported_languages() -> tuple:
    """Return tuple of supported language codes."""
    return _SUPPORTED_LANGS


def reload_translations():
    """Force reload translation files (useful for testing)."""
    global _TRANSLATIONS
    _TRANSLATIONS = {}
    _load_translations()

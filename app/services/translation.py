"""Translation service — currently disabled (no-op).

All translate_* functions return original text unchanged.
The function signatures are preserved so callers don't need changes.

To re-enable translation in the future:
1. Set TRANSLATION_SERVICE env var to 'google' or 'deepl'
2. Set the corresponding API key env var
3. Uncomment the provider logic in translate_text()
"""
import logging

logger = logging.getLogger(__name__)

# Supported languages (kept for reference)
SUPPORTED_LANGUAGES = ['lv', 'en', 'ru']


def is_translation_enabled() -> bool:
    """Translation is disabled — always returns False."""
    return False


def translate_text(text: str, target_lang: str) -> str:
    """Return original text unchanged (translation disabled)."""
    return text


def translate_task(task_dict: dict, target_lang: str) -> dict:
    """Return task unchanged (translation disabled)."""
    return task_dict


def translate_offering(offering_dict: dict, target_lang: str) -> dict:
    """Return offering unchanged (translation disabled)."""
    return offering_dict

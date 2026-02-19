"""Shared constants for the application."""

from app.constants.categories import (
    VALID_CATEGORIES,
    LEGACY_CATEGORY_MAP,
    normalize_category,
    validate_category,
)

__all__ = [
    'VALID_CATEGORIES',
    'LEGACY_CATEGORY_MAP',
    'normalize_category',
    'validate_category',
]

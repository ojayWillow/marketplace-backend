"""Category constants — single source of truth for the backend.

Must stay in sync with:
  frontend: packages/shared/src/constants/categories.ts
"""

# The 15 valid category keys (excluding 'all' which is filter-only)
VALID_CATEGORIES = {
    'cleaning',
    'moving',
    'assembly',
    'handyman',
    'plumbing',
    'electrical',
    'painting',
    'outdoor',
    'delivery',
    'care',
    'tutoring',
    'tech',
    'beauty',
    'events',
    'other',
}

# Legacy key -> current key mapping
# Mirrors frontend LEGACY_CATEGORY_MAP in categories.ts
LEGACY_CATEGORY_MAP = {
    # Old mobile categories
    'heavy-lifting': 'moving',
    'mounting': 'assembly',
    'construction': 'handyman',
    'repair': 'handyman',
    'repairs': 'handyman',
    'gardening': 'outdoor',
    'car-wash': 'outdoor',
    'snow-removal': 'outdoor',
    'pet-care': 'care',
    'babysitting': 'care',
    'childcare': 'care',
    'elderly-care': 'care',
    'shopping': 'delivery',
    'errands': 'delivery',
    'tech-help': 'tech',
    'tech-support': 'tech',
    'techsupport': 'tech',
    'hospitality': 'events',
    'music': 'events',
    'cooking': 'events',
    'catering': 'events',
    'photography': 'other',
    'translation': 'other',
    'fitness': 'other',
    'driving': 'delivery',
    'driver': 'delivery',
    'transport': 'delivery',
    'cleaning-services': 'cleaning',
    'house-cleaning': 'cleaning',
    'dog-walking': 'care',
    'pet-sitting': 'care',
    'lawn-care': 'outdoor',
    'yard-work': 'outdoor',
    'furniture-assembly': 'assembly',
    'ikea': 'assembly',
}


def normalize_category(category: str) -> str:
    """Normalize a category key.

    - Lowercases and strips whitespace
    - Converts legacy keys to their current equivalents
    - Returns the key as-is if it's already valid or unknown
    """
    key = category.lower().strip()
    return LEGACY_CATEGORY_MAP.get(key, key)


def validate_category(category: str) -> tuple[str, str | None]:
    """Validate and normalize a category.

    Returns:
        (normalized_key, error_message)
        error_message is None when valid.
    """
    normalized = normalize_category(category)
    if normalized not in VALID_CATEGORIES:
        return normalized, (
            f"Invalid category '{category}'. "
            f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    return normalized, None

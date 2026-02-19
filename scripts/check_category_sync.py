#!/usr/bin/env python3
"""
Category Sync Check

Extracts VALID_CATEGORIES from app/constants/categories.py
and verifies they match the expected canonical list.

If you're adding/removing/renaming a category:
1. Update app/constants/categories.py (VALID_CATEGORIES + LEGACY_CATEGORY_MAP)
2. Update EXPECTED_CATEGORIES below
3. Update frontend: packages/shared/src/constants/categories.ts
4. Update frontend translation files (en + lv) if labels changed
"""

import sys
import os

# -- Expected canonical categories (keep sorted) --
# This is the contract. Both frontend and backend must match.
EXPECTED_CATEGORIES = sorted([
    'assembly',
    'beauty',
    'care',
    'cleaning',
    'delivery',
    'electrical',
    'events',
    'handyman',
    'moving',
    'other',
    'outdoor',
    'painting',
    'plumbing',
    'tech',
    'tutoring',
])


def extract_valid_categories():
    """Import VALID_CATEGORIES from the backend module."""
    # Add project root to path so we can import app modules
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

    from app.constants.categories import VALID_CATEGORIES
    return sorted(VALID_CATEGORIES)


def main():
    print('\n\U0001f50d Category Sync Check\n')

    try:
        actual = extract_valid_categories()
    except Exception as e:
        print(f'\u274c Failed to import VALID_CATEGORIES: {e}')
        sys.exit(1)

    expected = EXPECTED_CATEGORIES

    print(f'  Expected: {len(expected)} categories')
    print(f'  Found:    {len(actual)} categories\n')

    missing = [k for k in expected if k not in actual]
    extra = [k for k in actual if k not in expected]

    if not missing and not extra:
        print('\u2705 All categories aligned!\n')
        print(f'  Categories: {", ".join(expected)}')
        print('')
        print('  \u2139\ufe0f  Remember: frontend packages/shared/src/constants/categories.ts must match too.')
        print('')
        sys.exit(0)
    else:
        if missing:
            print(f'\u274c Missing from categories.py: {", ".join(missing)}')
            print('   \u2192 Add these to VALID_CATEGORIES in app/constants/categories.py')
        if extra:
            print(f'\u274c Extra in categories.py (not in expected list): {", ".join(extra)}')
            print('   \u2192 Update EXPECTED_CATEGORIES in scripts/check_category_sync.py')
            print('   \u2192 Update frontend packages/shared/src/constants/categories.ts')
            print('   \u2192 Update frontend translation files (en + lv)')
        print('')
        print('\U0001f4cb To fix: update both the source file AND the expected list,')
        print('   then sync frontend packages/shared/src/constants/categories.ts.')
        print('')
        sys.exit(1)


if __name__ == '__main__':
    main()

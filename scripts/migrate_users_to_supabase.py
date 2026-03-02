#!/usr/bin/env python3
"""One-time migration script: create Supabase Auth users for existing local users.

Usage:
    # Dry run (no changes made)
    python scripts/migrate_users_to_supabase.py --dry-run

    # Actual migration
    python scripts/migrate_users_to_supabase.py

    # With custom batch size
    python scripts/migrate_users_to_supabase.py --batch-size 50

Requires:
    - SUPABASE_URL and SUPABASE_SERVICE_KEY env vars
    - DATABASE_URL env var (or SQLALCHEMY_DATABASE_URI)
    - Run from project root: python scripts/migrate_users_to_supabase.py

This script is idempotent: users who already have supabase_user_id are skipped.
"""

import sys
import os
import time
import argparse
import secrets
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

PLACEHOLDER_DOMAINS = ('@phone.kolab.local', '@supabase.kolab.local')


def is_placeholder_email(email):
    """Check if email is a placeholder (not a real user email)."""
    if not email:
        return True
    return any(email.endswith(d) for d in PLACEHOLDER_DOMAINS)


def migrate_users(dry_run=False, batch_size=25):
    """Migrate all local users to Supabase Auth."""
    from app import create_app, db
    from app.models import User

    app = create_app()

    with app.app_context():
        # Verify Supabase is configured
        if not dry_run:
            try:
                from app.services.supabase_client import get_supabase_client
                client = get_supabase_client()
                if not client:
                    logger.error('Supabase client not available. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.')
                    sys.exit(1)
            except Exception as e:
                logger.error(f'Failed to initialize Supabase client: {e}')
                sys.exit(1)

        # Get users without supabase_user_id
        users = User.query.filter(
            User.supabase_user_id.is_(None)
        ).order_by(User.id).all()

        total = len(users)
        logger.info(f'Found {total} users without supabase_user_id')

        if total == 0:
            logger.info('Nothing to migrate!')
            return

        if dry_run:
            logger.info('=== DRY RUN MODE === No changes will be made.')

        stats = {
            'success': 0,
            'skipped': 0,
            'failed': 0,
            'already_exists': 0,
        }
        errors = []

        for i, user in enumerate(users, 1):
            real_email = user.email if not is_placeholder_email(user.email) else None
            phone = user.phone

            if not real_email and not phone:
                logger.warning(f'  [{i}/{total}] User {user.id} ({user.username}): no email or phone, skipping')
                stats['skipped'] += 1
                continue

            identifier = real_email or phone
            logger.info(f'  [{i}/{total}] User {user.id} ({user.username}): {identifier}')

            if dry_run:
                stats['success'] += 1
                continue

            try:
                from app.services.supabase_auth import (
                    create_supabase_user,
                    get_supabase_user_by_email,
                    get_supabase_user_by_phone,
                )

                # Check if Supabase user already exists
                existing = None
                if real_email:
                    existing = get_supabase_user_by_email(real_email)
                if not existing and phone:
                    existing = get_supabase_user_by_phone(phone)

                if existing:
                    user.supabase_user_id = str(existing.id)
                    db.session.commit()
                    logger.info(f'    -> Linked to existing Supabase user {existing.id}')
                    stats['already_exists'] += 1
                    continue

                # Create new Supabase user
                supabase_user = create_supabase_user(
                    email=real_email,
                    phone=phone,
                    password=secrets.token_urlsafe(32),
                    email_confirm=True,
                    phone_confirm=True,
                    user_metadata={
                        'local_user_id': user.id,
                        'username': user.username,
                        'migrated': True,
                    },
                )

                user.supabase_user_id = str(supabase_user.id)
                db.session.commit()
                logger.info(f'    -> Created Supabase user {supabase_user.id}')
                stats['success'] += 1

            except Exception as e:
                error_msg = str(e)
                logger.error(f'    -> FAILED: {error_msg}')
                errors.append({'user_id': user.id, 'username': user.username, 'error': error_msg})
                stats['failed'] += 1
                db.session.rollback()

            # Rate limiting: pause between batches
            if i % batch_size == 0 and i < total:
                logger.info(f'  ... Pausing 2s after batch ({i}/{total}) ...')
                time.sleep(2)

        # Summary
        logger.info('\n' + '=' * 50)
        logger.info('MIGRATION SUMMARY')
        logger.info('=' * 50)
        logger.info(f'Total users processed: {total}')
        logger.info(f'Successfully created:  {stats["success"]}')
        logger.info(f'Already existed:       {stats["already_exists"]}')
        logger.info(f'Skipped (no contact):  {stats["skipped"]}')
        logger.info(f'Failed:                {stats["failed"]}')

        if errors:
            logger.info('\nFailed users:')
            for err in errors:
                logger.info(f'  User {err["user_id"]} ({err["username"]}): {err["error"]}')

        if dry_run:
            logger.info('\n(Dry run — no actual changes were made)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate existing users to Supabase Auth')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--batch-size', type=int, default=25, help='Users per batch (default: 25)')
    args = parser.parse_args()

    migrate_users(dry_run=args.dry_run, batch_size=args.batch_size)

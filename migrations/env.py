from __future__ import with_statement
import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

from alembic import context

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models import *

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# add your model's MetaData object here
app = create_app()
target_metadata = db.metadata

# Get database URL from Flask app config
def get_url():
    """Get database URL from Flask app configuration."""
    with app.app_context():
        url = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not url:
            # Fallback to environment variable
            url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
        if not url:
            # Default to SQLite for local development
            url = 'sqlite:///marketplace.db'
        # Handle Render's postgres:// vs postgresql:// issue
        if url and url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    # Get URL from Flask app instead of alembic.ini
    url = get_url()
    
    # Create engine directly with the URL from Flask app
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

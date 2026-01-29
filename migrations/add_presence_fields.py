"""Migration script to add presence tracking fields to users table.

Run this to add is_online and socket_id fields to existing database.

Usage:
    python migrations/add_presence_fields.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add presence tracking fields to users table."""
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("Starting migration: add_presence_fields")
            
            # Check if columns already exist
            result = db.session.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            # Add is_online column if it doesn't exist
            if 'is_online' not in columns:
                logger.info("Adding is_online column...")
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN is_online BOOLEAN DEFAULT 0 NOT NULL"
                ))
                db.session.commit()
                logger.info("✅ Added is_online column")
            else:
                logger.info("⏭️  is_online column already exists")
            
            # Add socket_id column if it doesn't exist
            if 'socket_id' not in columns:
                logger.info("Adding socket_id column...")
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN socket_id VARCHAR(100)"
                ))
                db.session.commit()
                logger.info("✅ Added socket_id column")
            else:
                logger.info("⏭️  socket_id column already exists")
            
            logger.info("\n✅ Migration completed successfully!")
            logger.info("\nNew columns added:")
            logger.info("  - is_online (BOOLEAN): Tracks real-time Socket.IO connection status")
            logger.info("  - socket_id (VARCHAR): Stores current Socket.IO session ID")
            
        except Exception as e:
            logger.error(f"\n❌ Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()

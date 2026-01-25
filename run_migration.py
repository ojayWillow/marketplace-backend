#!/usr/bin/env python3
"""Run database migration for message attachments."""

from app import create_app, db
from sqlalchemy import text

def run_migration():
    """Add attachment fields to messages table."""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            result = db.session.execute(text(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'messages' 
                AND column_name IN ('attachment_url', 'attachment_type')
                """
            ))
            existing_columns = [row[0] for row in result]
            
            if 'attachment_url' in existing_columns and 'attachment_type' in existing_columns:
                print("✅ Migration already applied! Columns already exist.")
                return
            
            print("📝 Running migration: Adding attachment fields to messages table...")
            
            # Add attachment_url column if not exists
            if 'attachment_url' not in existing_columns:
                db.session.execute(text(
                    "ALTER TABLE messages ADD COLUMN attachment_url VARCHAR(500)"
                ))
                print("✅ Added attachment_url column")
            
            # Add attachment_type column if not exists
            if 'attachment_type' not in existing_columns:
                db.session.execute(text(
                    "ALTER TABLE messages ADD COLUMN attachment_type VARCHAR(20)"
                ))
                print("✅ Added attachment_type column")
            
            db.session.commit()
            print("\n🎉 Migration completed successfully!")
            print("\nMessages can now include attachments (images, files, videos, audio)")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {e}")
            raise

if __name__ == '__main__':
    run_migration()

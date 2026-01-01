#!/usr/bin/env python
"""Database initialization script for marketplace backend.

This script creates all database tables based on the SQLAlchemy models.
Run this once before starting the application for the first time.

Usage:
    python init_db.py
"""

import os
import sys
from app import create_app, db

def init_database():
    """Initialize the database by creating all tables."""
    
    # Create Flask app
    config_name = os.getenv('FLASK_ENV', 'development')
    app = create_app(config_name)
    
    print(f"\n{'='*60}")
    print(f"Database Initialization for {config_name.upper()} Environment")
    print(f"{'='*60}\n")
    
    # Push app context
    with app.app_context():
        try:
            print("Creating database tables...")
            print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}\n")
            
            # Create all tables
            db.create_all()
            
            print("\u2705 Database tables created successfully!\n")
            
            # List all tables
            from app.models import User, Listing, TaskRequest, TaskResponse, Review
            
            tables_info = [
                ("users", "User accounts and authentication"),
                ("listings", "Buy/Sell marketplace items"),
                ("task_requests", "Quick help job requests"),
                ("task_responses", "Responses to help requests"),
                ("reviews", "User ratings and reviews"),
            ]
            
            print("Created tables:")
            for table_name, description in tables_info:
                print(f"  ✓ {table_name:<25} - {description}")
            
            print(f"\n{'='*60}")
            print("✅ Database initialization complete!")
            print(f"{'='*60}\n")
            print("Next steps:")
            print("  1. Start the Flask server: python wsgi.py")
            print("  2. Test registration endpoint: POST /api/auth/register")
            print("\n")
            
            return True
            
        except Exception as e:
            print(f"\u274c Error creating database: {e}\n")
            print(f"Traceback: {type(e).__name__}: {str(e)}")
            return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)

"""Database reset script for development.

This script drops all tables and recreates them with the current schema.
USE ONLY IN DEVELOPMENT - this will delete all data!

Usage:
    python reset_db.py
"""

import os
import sys

# Confirm before proceeding
print("="*60)
print("WARNING: This will DELETE ALL DATA in the database!")
print("This should only be used in development.")
print("="*60)

confirm = input("Type 'yes' to confirm: ")
if confirm.lower() != 'yes':
    print("Aborted.")
    sys.exit(0)

from app import create_app, db

app = create_app()

with app.app_context():
    print("\nDropping all tables...")
    db.drop_all()
    
    print("Creating all tables with current schema...")
    db.create_all()
    
    print("\nDatabase reset complete!")
    print("You can now start the server with: python run.py")

#!/usr/bin/env python
"""Debug script to run migrations with verbose output."""
import sys
import traceback
from app import create_app, db
from flask_migrate import upgrade

try:
    print("[DEBUG] Creating Flask app...")
    app = create_app('production')
    
    with app.app_context():
        print("[DEBUG] App context created")
        print(f"[DEBUG] Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')[:50]}...")
        
        try:
            print("[DEBUG] Running migrations...")
            upgrade()
            print("[DEBUG] Migrations completed successfully!")
        except Exception as e:
            print(f"[ERROR] Migration failed: {e}")
            print(f"[ERROR] Type: {type(e).__name__}")
            traceback.print_exc()
            sys.exit(1)
            
except Exception as e:
    print(f"[ERROR] Failed to create app: {e}")
    traceback.print_exc()
    sys.exit(1)

print("[DEBUG] All done!")

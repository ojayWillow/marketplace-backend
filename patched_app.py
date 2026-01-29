"""
Gevent-patched application entrypoint.

This file ensures gevent.monkey.patch_all() runs BEFORE any SSL/socket imports,
preventing RecursionError in push notifications and other async operations.

IMPORTANT: This must be imported before any other modules that use SSL/requests/urllib3.
"""

# Monkey-patch FIRST, before ANY other imports
from gevent import monkey
monkey.patch_all()

# Now safe to import the app
from app import create_app, socketio

# Create the application instance
# Gunicorn will call this as: patched_app:application
application = create_app()

# For compatibility, also expose as 'app'
app = application

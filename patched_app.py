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
application = create_app()

# For compatibility, also expose as 'app'
app = application

# CRITICAL: Wrap the Flask app with SocketIO's WSGI middleware
# This ensures Socket.IO connections are properly handled by gunicorn + gevent
# Without this, Socket.IO polling/websocket requests timeout
wsgi_app = socketio.WSGIApp(socketio, application)

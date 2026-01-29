#!/bin/bash
set -e

echo "Starting application..."

# Set default PORT if not set
export PORT=${PORT:-10000}

# Run migrations first (blocking) - this ensures DB is ready
echo "Running database migrations..."
flask db upgrade 2>&1 | sed 's/^/[MIGRATION] /' || echo "[MIGRATION] Warning: migrations may have failed"
echo "[MIGRATION] Completed"

# Start gunicorn with gevent worker for async support
# Flask-SocketIO with async_mode='gevent' handles Socket.IO connections internally
echo "Starting gunicorn on port $PORT..."
exec gunicorn patched_app:application \
    --worker-class gevent \
    -w 1 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --log-level info

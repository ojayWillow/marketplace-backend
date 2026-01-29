#!/bin/bash
set -e

echo "Starting application..."

# Set default PORT if not set
export PORT=${PORT:-10000}

# Run migrations first (blocking) - this ensures DB is ready
echo "Running database migrations..."
flask db upgrade 2>&1 | sed 's/^/[MIGRATION] /' || echo "[MIGRATION] Warning: migrations may have failed"
echo "[MIGRATION] Completed"

# Start gunicorn with gevent-websocket worker for Socket.IO support
echo "Starting gunicorn with gevent worker on port $PORT..."
exec gunicorn patched_app:application \
    --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    -w 1 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --log-level info

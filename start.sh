#!/bin/bash
set -e

echo "Starting application..."

# Run migrations in background (non-blocking)
echo "Running database migrations in background..."
(flask db upgrade 2>&1 | sed 's/^/[MIGRATION] /' && echo "[MIGRATION] Completed successfully") &

# Wait a moment for migrations to start
sleep 2

# Start gunicorn with patched entrypoint to prevent RecursionError
echo "Starting gunicorn with gevent monkey-patched entrypoint..."
exec gunicorn patched_app:application --worker-class gevent -w 1 --bind 0.0.0.0:$PORT --log-level info

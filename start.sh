#!/bin/bash
set -e

echo "Starting application..."

# Run migrations in background (non-blocking)
echo "Running database migrations in background..."
(flask db upgrade 2>&1 | sed 's/^/[MIGRATION] /' && echo "[MIGRATION] Completed successfully") &

# Wait a moment for migrations to start
sleep 2

# Start gunicorn immediately
echo "Starting gunicorn..."
exec gunicorn wsgi:app --worker-class gevent -w 1 --bind 0.0.0.0:$PORT --log-level info

#!/bin/bash
set -e

echo "Starting application..."

# Set default PORT if not set
export PORT=${PORT:-10000}

# Hotfix: add difficulty column if it doesn't exist (Alembic migration was silently failing)
echo "[HOTFIX] Ensuring difficulty column exists..."
python -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(\"ALTER TABLE task_requests ADD COLUMN IF NOT EXISTS difficulty VARCHAR(20) NOT NULL DEFAULT 'medium'\")
    print('[HOTFIX] difficulty column ready')
    conn.close()
except Exception as e:
    print(f'[HOTFIX] Warning: {e}')
" 2>&1 || echo "[HOTFIX] Warning: hotfix script failed"

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

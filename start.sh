#!/bin/bash
set -e

echo "Starting application..."

# Set default PORT if not set (Railway injects this in production)
export PORT=${PORT:-5000}

# Stamp Alembic version if DB was created via db.create_all() (no migration history)
# This prevents Alembic from trying to replay all migrations on an already-populated DB
echo "[ALEMBIC] Checking migration state..."
python -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
    # Check if alembic_version table exists and has any rows
    cur.execute(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')\")
    table_exists = cur.fetchone()[0]
    
    if table_exists:
        cur.execute('SELECT COUNT(*) FROM alembic_version')
        count = cur.fetchone()[0]
        if count == 0:
            print('[ALEMBIC] alembic_version is empty - DB was created via db.create_all()')  
            print('[ALEMBIC] Stamping current head: merge_all_heads_feb2026')
            cur.execute(\"INSERT INTO alembic_version (version_num) VALUES ('merge_all_heads_feb2026')\")
            print('[ALEMBIC] Stamped successfully - migrations are now in sync')
        else:
            cur.execute('SELECT version_num FROM alembic_version')
            version = cur.fetchone()[0]
            print(f'[ALEMBIC] Current version: {version}')
    else:
        print('[ALEMBIC] No alembic_version table - creating and stamping...')
        cur.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))')
        cur.execute(\"INSERT INTO alembic_version (version_num) VALUES ('merge_all_heads_feb2026')\")
        print('[ALEMBIC] Created and stamped to merge_all_heads_feb2026')
    
    conn.close()
except Exception as e:
    print(f'[ALEMBIC] Warning: {e}')
" 2>&1 || echo "[ALEMBIC] Warning: stamp check failed"

# Run migrations (should be a no-op if stamp was applied, or apply new migrations)
echo "Running database migrations..."
flask db upgrade 2>&1 | sed 's/^/[MIGRATION] /' || echo "[MIGRATION] Warning: migrations may have failed"
echo "[MIGRATION] Completed"

# Start gunicorn with gevent worker for async support
# Flask-SocketIO with async_mode='gevent' handles Socket.IO connections internally
# NOTE: Using 1 worker because Socket.IO polling transport requires sticky sessions.
# Railway's load balancer doesn't support sticky sessions, so multiple workers
# cause 400 errors when poll requests land on a different worker than the handshake.
# Redis message queue is still configured for future multi-worker support.
echo "Starting gunicorn on port $PORT..."
exec gunicorn patched_app:application \
    --worker-class gevent \
    -w 1 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --log-level info

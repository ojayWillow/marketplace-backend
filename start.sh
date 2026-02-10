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

# Hotfix: ensure notifications table exists (was missing due to unmerged Alembic heads)
echo "[HOTFIX] Ensuring notifications table exists..."
python -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            data TEXT,
            related_type VARCHAR(50),
            related_id INTEGER,
            is_read BOOLEAN DEFAULT FALSE,
            read_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(is_read)')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON notifications(user_id, is_read)')
    print('[HOTFIX] notifications table ready')
    conn.close()
except Exception as e:
    print(f'[HOTFIX] Warning: {e}')
" 2>&1 || echo "[HOTFIX] Warning: notifications hotfix failed"

# Hotfix: ensure password_reset_tokens table exists
echo "[HOTFIX] Ensuring password_reset_tokens table exists..."
python -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token VARCHAR(100) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    ''')
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token ON password_reset_tokens(token)')
    print('[HOTFIX] password_reset_tokens table ready')
    conn.close()
except Exception as e:
    print(f'[HOTFIX] Warning: {e}')
" 2>&1 || echo "[HOTFIX] Warning: password_reset_tokens hotfix failed"

# Hotfix: ensure disputes table exists
echo "[HOTFIX] Ensuring disputes table exists..."
python -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS disputes (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES task_requests(id),
            filed_by_id INTEGER NOT NULL REFERENCES users(id),
            filed_against_id INTEGER NOT NULL REFERENCES users(id),
            reason VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            evidence_images JSON,
            status VARCHAR(20) NOT NULL DEFAULT '"'"'open'"'"',
            resolution VARCHAR(20),
            resolution_notes TEXT,
            resolved_by_id INTEGER REFERENCES users(id),
            resolved_at TIMESTAMP,
            response_description TEXT,
            response_images JSON,
            responded_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_disputes_task_id ON disputes(task_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_disputes_status ON disputes(status)')
    print('[HOTFIX] disputes table ready')
    conn.close()
except Exception as e:
    print(f'[HOTFIX] Warning: {e}')
" 2>&1 || echo "[HOTFIX] Warning: disputes hotfix failed"

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

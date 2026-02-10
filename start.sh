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

# Hotfix: ensure notifications table and ALL its columns exist
echo "[HOTFIX] Ensuring notifications table and columns exist..."
python -c "
import os, psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.autocommit = True
    cur = conn.cursor()
    # Create table if it doesn't exist
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
    # Ensure all columns exist (table may have been created without some columns)
    cur.execute('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS data TEXT')
    cur.execute('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_type VARCHAR(50)')
    cur.execute('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS related_id INTEGER')
    cur.execute('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE')
    cur.execute('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at TIMESTAMP')
    cur.execute('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()')
    # Create indexes
    cur.execute('CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(is_read)')
    cur.execute('CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON notifications(user_id, is_read)')
    print('[HOTFIX] notifications table and all columns ready')
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

# Run migrations (should be a no-op now if stamp was applied, or apply new migrations)
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

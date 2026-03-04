from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO()

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Determine environment
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # ── JSON encoding: preserve emoji / Unicode in responses ────────────
    app.config['JSON_AS_ASCII'] = False
    
    # Get database URL from environment
    database_url = (
        os.environ.get('DATABASE_URL') 
        or os.environ.get('SQLALCHEMY_DATABASE_URI')
    )
    
    # Handle Render's postgres:// vs postgresql:// issue
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Configuration based on environment
    if config_name == 'testing':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
    elif database_url:
        # Production/Render - use the environment database URL
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Local development fallback
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///marketplace.db'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Allowed origins for CORS
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8081",  # Expo dev
        "https://marketplace-frontend-tau-seven.vercel.app",
        "https://marketplace-backend-qmh6.onrender.com",  # Old Render backend
        "https://marketplace-backend-production-e808.up.railway.app",  # Railway backend
        "https://www.kolab.lv",  # Production frontend
        "https://kolab.lv",  # Production frontend (non-www)
    ]
    
    # Add custom frontend URL if set
    frontend_url = os.environ.get('FRONTEND_URL', '')
    if frontend_url:
        allowed_origins.append(frontend_url)
    
    # In development, allow all origins for easier mobile testing
    is_development = config_name == 'development' or os.environ.get('FLASK_DEBUG') == '1'
    
    # Socket.IO CORS: In production, allow specific origins + Railway backend URL
    # The mobile app connects FROM the Railway URL, so we need to allow it
    socket_cors_origins = "*" if is_development else allowed_origins
    
    # Socket.IO async mode:
    # - Production: 'gevent' (required by gunicorn gevent worker)
    # - Testing: 'threading' (gevent not installed in test env)
    socket_async_mode = 'threading' if config_name == 'testing' else 'gevent'
    
    # Initialize Socket.IO
    # IMPORTANT: Using polling transport ONLY because gunicorn's standard gevent worker
    # does not support WebSocket protocol. WebSocket would require geventwebsocket worker.
    # Polling is reliable and works perfectly for real-time messaging.
    socketio.init_app(app, 
                     cors_allowed_origins=socket_cors_origins,
                     async_mode=socket_async_mode,
                     logger=not app.config.get('TESTING', False),
                     engineio_logger=False,
                     ping_timeout=60,
                     ping_interval=25,
                     allow_upgrades=False)  # MUST be False - gunicorn gevent can't handle WebSocket
    
    # Register socket events
    from app.socket_events import register_socket_events
    register_socket_events(socketio)
    
    # CRITICAL FIX: Import models at module level BEFORE creating tables
    # This ensures SQLAlchemy knows about all models when db.create_all() is called
    from app.models import (
        User, TaskRequest, TaskApplication, Listing, Review, 
        Message, Conversation, Notification, Offering, 
        Favorite, PushSubscription, Dispute, Payment
    )
    
    # Auto-create tables and constraints on startup
    with app.app_context():
        try:
            # Create all tables - models are now properly registered
            db.create_all()
            print("[STARTUP] Database tables created/verified successfully")
            
            # Verify critical tables exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"[STARTUP] Tables in database: {tables}")
            
            if 'conversations' not in tables or 'messages' not in tables:
                print("[STARTUP] WARNING: Messages tables not created! Attempting manual creation...")
                # Force create the tables
                Conversation.__table__.create(db.engine, checkfirst=True)
                Message.__table__.create(db.engine, checkfirst=True)
                print("[STARTUP] Messages tables created manually")
            
            # MIGRATION: Add attachment columns to messages table if they don't exist
            # Skip for SQLite (testing) since db.create_all() handles it
            if not app.config.get('TESTING', False):
                try:
                    columns = [col['name'] for col in inspector.get_columns('messages')]
                    print(f"[STARTUP] Messages table columns: {columns}")
                    
                    if 'attachment_url' not in columns:
                        print("[STARTUP] Adding attachment_url column to messages table...")
                        db.session.execute(db.text('ALTER TABLE messages ADD COLUMN attachment_url TEXT'))
                        db.session.commit()
                        print("[STARTUP] ✓ Added attachment_url column")
                    
                    if 'attachment_type' not in columns:
                        print("[STARTUP] Adding attachment_type column to messages table...")
                        db.session.execute(db.text('ALTER TABLE messages ADD COLUMN attachment_type VARCHAR(20)'))
                        db.session.commit()
                        print("[STARTUP] ✓ Added attachment_type column")
                        
                except Exception as migration_error:
                    print(f"[STARTUP] Migration error: {migration_error}")
                    import traceback
                    traceback.print_exc()
            else:
                columns = [col['name'] for col in inspector.get_columns('messages')]
                print(f"[STARTUP] Messages table columns: {columns}")
            
            # MIGRATION: Add supabase_user_id column to users table if it doesn't exist
            if not app.config.get('TESTING', False):
                try:
                    user_columns = [col['name'] for col in inspector.get_columns('users')]
                    if 'supabase_user_id' not in user_columns:
                        print("[STARTUP] Adding supabase_user_id column to users table...")
                        db.session.execute(db.text(
                            'ALTER TABLE users ADD COLUMN supabase_user_id VARCHAR(36) UNIQUE'
                        ))
                        db.session.execute(db.text(
                            'CREATE INDEX IF NOT EXISTS ix_users_supabase_user_id ON users (supabase_user_id)'
                        ))
                        db.session.commit()
                        print("[STARTUP] ✓ Added supabase_user_id column")
                except Exception as e:
                    print(f"[STARTUP] supabase_user_id migration note: {e}")
            
            # MIGRATION: Rename revolut_order_id -> stripe_session_id in payments table
            if not app.config.get('TESTING', False):
                try:
                    if 'payments' in tables:
                        payment_columns = [col['name'] for col in inspector.get_columns('payments')]
                        if 'revolut_order_id' in payment_columns and 'stripe_session_id' not in payment_columns:
                            print("[STARTUP] Renaming revolut_order_id -> stripe_session_id in payments table...")
                            db.session.execute(db.text(
                                'ALTER TABLE payments RENAME COLUMN revolut_order_id TO stripe_session_id'
                            ))
                            db.session.execute(db.text(
                                'ALTER TABLE payments ALTER COLUMN stripe_session_id TYPE VARCHAR(200)'
                            ))
                            db.session.commit()
                            print("[STARTUP] ✓ Renamed revolut_order_id to stripe_session_id")
                except Exception as e:
                    print(f"[STARTUP] payments migration note: {e}")
            
            # Add unique constraint for task applications (prevent duplicate applications)
            # Note: TaskApplication model already defines this via __table_args__,
            # so db.create_all() handles it. This is just a safety net for production.
            if not app.config.get('TESTING', False):
                try:
                    db.session.execute(db.text('CREATE UNIQUE INDEX IF NOT EXISTS unique_task_application ON task_applications (task_id, applicant_id)'))
                    db.session.commit()
                    print("[STARTUP] Unique constraints created successfully")
                except Exception as e:
                    print(f"[STARTUP] Constraint note: {e}")
            else:
                print("[STARTUP] Unique constraints created successfully")
                
        except Exception as e:
            print(f"[STARTUP] Database initialization error: {e}")
            import traceback
            traceback.print_exc()
    
    # CORS configuration - allow frontend origins
    # In development, be more permissive for mobile testing
    cors_origins = "*" if is_development else allowed_origins
    
    CORS(app, 
         origins=cors_origins,
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "Accept"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    
    # Middleware to update user's last_seen on authenticated requests
    @app.before_request
    def update_last_seen():
        """Update user's last_seen timestamp on every authenticated request."""
        # Skip for OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return
        
        # Skip for public endpoints
        public_paths = ['/health', '/api/auth/login', '/api/auth/register']
        if any(request.path.startswith(path) for path in public_paths):
            return
        
        # Try to get authenticated user and update last_seen
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return
            
            from app.utils.auth import _resolve_user_from_token
            user_id, error, status = _resolve_user_from_token(auth_header)
            if error or not user_id:
                return
            
            from app.models import User
            user = User.query.get(user_id)
            if user:
                user.update_last_seen()
                db.session.commit()
        except Exception:
            # Silently ignore errors - don't break the request
            pass
    
    # Health check route with debug info
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            'status': 'ok',
            'environment': config_name,
            'database_configured': bool(app.config.get('SQLALCHEMY_DATABASE_URI')),
        }), 200
    
    # Register blueprints
    try:
        from app.routes import register_routes
        register_routes(app)
        print("[STARTUP] Routes registered successfully")
    except Exception as e:
        print(f"ERROR registering routes: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    return app

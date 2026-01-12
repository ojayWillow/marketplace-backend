"""Routes package for the marketplace application."""

from flask import Blueprint, jsonify

# Create a simple health blueprint for /api/health
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def api_health():
    """Health check endpoint at /api/health"""
    return jsonify({
        'status': 'ok',
        'message': 'Backend is running!',
        'version': '1.0.0'
    }), 200

def register_routes(app):
    """Register all route blueprints with the application."""
    from .auth import auth_bp
    from .listings import listings_bp
    from .tasks import tasks_bp
    from .reviews import reviews_bp
    from .task_responses import task_responses_bp
    from .uploads import uploads_bp
    from .messages import messages_bp
    from .helpers import helpers_bp
    from .offerings import offerings_bp
    from .favorites import favorites_bp
    from .admin import admin_bp
    from .notifications import notifications_bp

    # Register health check at /api/health
    app.register_blueprint(health_bp, url_prefix='/api')
    
    # Register all other blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(listings_bp, url_prefix='/api/listings')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(task_responses_bp, url_prefix='/api/task_responses')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    app.register_blueprint(helpers_bp, url_prefix='/api/helpers')
    app.register_blueprint(offerings_bp, url_prefix='/api/offerings')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(favorites_bp)  # Routes already have /api/favorites prefix
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

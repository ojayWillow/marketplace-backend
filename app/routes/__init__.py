"""Routes package for the marketplace application."""

from flask import Blueprint

def register_routes(app):
    """Register all route blueprints with the application."""
    from .auth import auth_bp
    from .listings import listings_bp
    from .tasks import tasks_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(listings_bp, url_prefix='/api/listings')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')

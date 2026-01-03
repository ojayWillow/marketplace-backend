"""Routes package for the marketplace application."""

from flask import Blueprint

def register_routes(app):
    """Register all route blueprints with the application."""
    from .auth import auth_bp
    from .listings import listings_bp
    from .tasks import tasks_bp
    from .reviews import reviews_bp
    from .task_responses import task_responses_bp
    from .uploads import uploads_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(listings_bp, url_prefix='/api/listings')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(task_responses_bp, url_prefix='/api/task_responses')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')

"""Routes package for the marketplace application."""


def register_routes(app):
    """Register all route blueprints with the application."""
    from .auth import auth_bp
    from .listings import listings_bp
    from .tasks import tasks_bp
    from .reviews import reviews_bp
    from .uploads import uploads_bp
    from .messages import messages_bp
    from .offerings import offerings_bp
    from .favorites import favorites_bp
    from .admin import admin_bp
    from .notifications import notifications_bp
    from .push import push_bp
    from .disputes import disputes_bp
    from .onboarding import onboarding_bp

    # Register all blueprints with consistent url_prefix pattern
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(listings_bp, url_prefix='/api/listings')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    app.register_blueprint(offerings_bp, url_prefix='/api/offerings')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(favorites_bp, url_prefix='/api/favorites')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    app.register_blueprint(push_bp, url_prefix='/api/push')
    app.register_blueprint(disputes_bp, url_prefix='/api/disputes')
    app.register_blueprint(onboarding_bp, url_prefix='/api/auth')

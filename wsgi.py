import os
from app import create_app, socketio

config_name = os.getenv('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    # Get port from environment (Railway injects this)
    port = int(os.getenv('PORT', 5000))
    
    # CRITICAL: Never run debug mode in production
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    # Run with socketio support
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode)

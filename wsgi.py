import os
from app import create_app, socketio

config_name = os.getenv('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    # Run with socketio support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

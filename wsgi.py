
#!/usr/bin/env python3
"""
WSGI entry point for System Control Dashboard
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app and SocketIO
from server_dashboard import create_app

# Create the Flask app
app, socketio = create_app()

# Export for gunicorn
application = app

if __name__ == "__main__":
    # For development
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)

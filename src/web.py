import os
from datetime import datetime
from flask import Flask

flask_app = Flask("CampusMonitoringHealth")

@flask_app.route('/')
def home():
    """Health check endpoint"""
    return {
        'status': 'alive',
        'bot': 'J3 Monitor',
        'timestamp': datetime.now().isoformat()
    }

@flask_app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok'}

def run_flask_server():
    """Run Flask server in background"""
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

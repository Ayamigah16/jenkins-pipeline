import os
import signal
import sys
from flask import Flask, jsonify

def create_app():
    app = Flask(__name__)

    # Externalized configuration via environment variables
    app.config['APP_HOST'] = os.getenv('APP_HOST', '0.0.0.0')
    app.config['APP_PORT'] = int(os.getenv('APP_PORT', '3000'))
    app.config['ENVIRONMENT'] = os.getenv('ENVIRONMENT', 'production')
    app.config['DEBUG_MODE'] = os.getenv('DEBUG', 'false').lower() == 'true'
    app.config['APP_NAME'] = os.getenv('APP_NAME', 'secure-flask-app')

    @app.route('/')
    def home():
        environment = app.config['ENVIRONMENT']
        return f"Hello from Docker! Running in {environment} mode."

    @app.route('/health')
    def health():
        return jsonify(
            status='healthy',
            environment=app.config['ENVIRONMENT'],
            app=app.config['APP_NAME'],
        ), 200

    return app


def _handle_shutdown(signum, frame):
    print(f"Received signal {signum}. Shutting down gracefully...", flush=True)
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    application = create_app()
    application.run(
        host=application.config['APP_HOST'],
        port=application.config['APP_PORT'],
        debug=application.config['DEBUG_MODE'],
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Control Dashboard Server
Main Flask application with SocketIO support
"""

# ۰. خیلی مهم: این خط باید اولین import باشه قبل از هر چیز.
from gevent import monkey
monkey.patch_all()

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template_string, request, jsonify, send_file
from flask_socketio import SocketIO, emit

from Config import get_config, validate_config

# ۱. SocketIO global instance
socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    config = get_config()
    app.config.from_object(config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    setup_logging(app)

    # ۲. Initialize SocketIO with the Flask app
    socketio.init_app(
        app,
        ping_timeout=app.config.get('SOCKETIO_PING_TIMEOUT', None),
        ping_interval=app.config.get('SOCKETIO_PING_INTERVAL', None),
        async_mode='gevent'
    )

    init_database()

    connected_clients = {}

    @app.route('/')
    def index():
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
          <title>Dashboard</title>
          <meta charset="utf-8">
          <style>
            .status { padding:10px; margin:10px 0; }
            .online { background: #d4edda; color: #155724; }
            .offline { background: #f8d7da; color: #721c24; }
          </style>
        </head>
        <body>
          <div id="status" class="offline">🔴 Disconnected</div>
          <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
          <script>
            const socket = io();
            socket.on('connect', () => {
              document.getElementById('status').className = 'online';
              document.getElementById('status').innerHTML = '🟢 Connected';
            });
            socket.on('disconnect', () => {
              document.getElementById('status').className = 'offline';
              document.getElementById('status').innerHTML = '🔴 Disconnected';
            });
            socket.on('client_update', data => {
              console.log('clients:', data.clients);
            });
            function refreshClients() { socket.emit('get_clients'); }
          </script>
        </body>
        </html>
        """)

    @socketio.on('connect')
    def on_connect():
        cid = request.sid
        connected_clients[cid] = {
            'id': cid, 'connected_at': datetime.utcnow().isoformat()
        }
        emit('client_update', {'clients': connected_clients}, broadcast=True)

    @socketio.on('disconnect')
    def on_disconnect():
        cid = request.sid
        connected_clients.pop(cid, None)
        emit('client_update', {'clients': connected_clients}, broadcast=True)

    @socketio.on('get_clients')
    def handle_get_clients():
        emit('client_update', {'clients': connected_clients})

    @app.route('/api/logs')
    def get_logs():
        log_file = app.config.get('LOG_FILE', 'dashboard.log')
        if os.path.exists(log_file):
            return send_file(log_file, as_attachment=True)
        return jsonify({'error': 'not found'}), 404

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'clients': len(connected_clients)})

    return app

def setup_logging(app):
    if not app.debug and not app.testing:
        log_dir = Path('logs'); log_dir.mkdir(exist_ok=True)
        fh = RotatingFileHandler(log_dir / app.config['LOG_FILE'], maxBytes=10**7, backupCount=5)
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        fh.setLevel(logging.INFO)
        app.logger.addHandler(fh)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Dashboard starting')

def init_database():
    try:
        conn = sqlite3.connect('dashboard.db')
        conn.execute('CREATE TABLE IF NOT EXISTS clients (id TEXT PRIMARY KEY, connected_at TEXT)')
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB init error:", e)

def main():
    errors = validate_config()
    if errors:
        print("Config errors:", errors)
        sys.exit(1)

    app = create_app()
    cfg = get_config()
    print(f"Starting on {cfg.HOST}:{cfg.PORT}")
    socketio.run(app, host=cfg.HOST, port=cfg.PORT, debug=cfg.DEBUG, use_reloader=False)

if __name__ == '__main__':
    main()

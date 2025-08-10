
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System Control Dashboard Server
Main Flask application with SocketIO support
"""

import os
import sys
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

# Flask imports
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit, disconnect
import eventlet

# Configuration
from Config import get_config, validate_config

# Initialize eventlet for better performance
eventlet.monkey_patch()

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    
    # Ensure required directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Setup logging
    setup_logging(app)
    
    # Initialize SocketIO
    socketio = SocketIO(
        app,
        cors_allowed_origins=app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'],
        ping_timeout=app.config['SOCKETIO_PING_TIMEOUT'],
        ping_interval=app.config['SOCKETIO_PING_INTERVAL'],
        async_mode='eventlet'
    )
    
    # Initialize database
    init_database()
    
    # Store connected clients
    connected_clients = {}
    
    @app.route('/')
    def index():
        """Main dashboard page"""
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>System Control Dashboard</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .header { text-align: center; margin-bottom: 30px; }
                .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
                .online { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
                .offline { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
                .clients { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
                .client-card { background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; }
                .client-header { font-weight: bold; margin-bottom: 10px; }
                .client-info { font-size: 0.9em; color: #666; }
                button { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin: 2px; }
                button:hover { background: #0056b3; }
                .danger { background: #dc3545; }
                .danger:hover { background: #c82333; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🖥️ System Control Dashboard</h1>
                    <div id="status" class="status offline">🔴 Disconnected</div>
                </div>
                
                <div class="section">
                    <h2>📊 Connected Clients</h2>
                    <div id="clients" class="clients">
                        <p>No clients connected</p>
                    </div>
                </div>
                
                <div class="section">
                    <h2>⚡ Quick Actions</h2>
                    <button onclick="refreshClients()">🔄 Refresh Clients</button>
                    <button onclick="sendBroadcast()">📢 Send Broadcast</button>
                    <button onclick="viewLogs()">📋 View Logs</button>
                </div>
            </div>

            <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
            <script>
                const socket = io();
                
                socket.on('connect', function() {
                    document.getElementById('status').className = 'status online';
                    document.getElementById('status').innerHTML = '🟢 Connected';
                    refreshClients();
                });
                
                socket.on('disconnect', function() {
                    document.getElementById('status').className = 'status offline';
                    document.getElementById('status').innerHTML = '🔴 Disconnected';
                });
                
                socket.on('client_update', function(data) {
                    updateClientsDisplay(data.clients);
                });
                
                function updateClientsDisplay(clients) {
                    const container = document.getElementById('clients');
                    if (Object.keys(clients).length === 0) {
                        container.innerHTML = '<p>No clients connected</p>';
                        return;
                    }
                    
                    let html = '';
                    for (let id in clients) {
                        const client = clients[id];
                        html += `
                            <div class="client-card">
                                <div class="client-header">💻 ${client.name || id}</div>
                                <div class="client-info">
                                    <div>📍 IP: ${client.ip || 'Unknown'}</div>
                                    <div>⏰ Connected: ${new Date(client.connected_at).toLocaleString()}</div>
                                    <div>💓 Last Ping: ${client.last_ping ? new Date(client.last_ping).toLocaleString() : 'Never'}</div>
                                </div>
                                <div style="margin-top: 10px;">
                                    <button onclick="sendCommand('${id}')">📝 Send Command</button>
                                    <button onclick="requestFiles('${id}')">📁 Get Files</button>
                                    <button onclick="disconnectClient('${id}')" class="danger">❌ Disconnect</button>
                                </div>
                            </div>
                        `;
                    }
                    container.innerHTML = html;
                }
                
                function refreshClients() {
                    socket.emit('get_clients');
                }
                
                function sendCommand(clientId) {
                    const command = prompt('Enter command to execute:');
                    if (command) {
                        socket.emit('send_command', {client_id: clientId, command: command});
                    }
                }
                
                function requestFiles(clientId) {
                    socket.emit('request_files', {client_id: clientId});
                }
                
                function disconnectClient(clientId) {
                    if (confirm('Disconnect this client?')) {
                        socket.emit('disconnect_client', {client_id: clientId});
                    }
                }
                
                function sendBroadcast() {
                    const message = prompt('Enter broadcast message:');
                    if (message) {
                        socket.emit('broadcast', {message: message});
                    }
                }
                
                function viewLogs() {
                    window.open('/api/logs', '_blank');
                }
            </script>
        </body>
        </html>
        """)
    
    @app.route('/api/health')
    def health_check():
        """Health check endpoint for monitoring"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'clients': len(connected_clients)
        })
    
    @app.route('/api/logs')
    def get_logs():
        """Get application logs"""
        try:
            log_file = app.config.get('LOG_FILE', 'dashboard.log')
            if os.path.exists(log_file):
                return send_file(log_file, as_attachment=True)
            else:
                return jsonify({'error': 'Log file not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @socketio.on('connect')
    def on_connect():
        """Handle client connection"""
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        app.logger.info(f"Client connected from {client_ip}")
        
        # Store client info
        connected_clients[request.sid] = {
            'id': request.sid,
            'ip': client_ip,
            'connected_at': datetime.utcnow().isoformat(),
            'last_ping': None,
            'name': f"Client-{request.sid[:8]}"
        }
        
        # Broadcast updated client list
        emit('client_update', {'clients': connected_clients}, broadcast=True)
    
    @socketio.on('disconnect')
    def on_disconnect():
        """Handle client disconnection"""
        if request.sid in connected_clients:
            client = connected_clients.pop(request.sid)
            app.logger.info(f"Client {client['name']} disconnected")
            
            # Broadcast updated client list
            emit('client_update', {'clients': connected_clients}, broadcast=True)
    
    @socketio.on('get_clients')
    def handle_get_clients():
        """Send current client list"""
        emit('client_update', {'clients': connected_clients})
    
    @socketio.on('ping')
    def handle_ping(data):
        """Handle client ping"""
        if request.sid in connected_clients:
            connected_clients[request.sid]['last_ping'] = datetime.utcnow().isoformat()
            if 'name' in data:
                connected_clients[request.sid]['name'] = data['name']
        
        emit('pong', {'timestamp': datetime.utcnow().isoformat()})
    
    return app, socketio

def setup_logging(app):
    """Setup application logging"""
    if not app.debug and not app.testing:
        # Create logs directory
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Setup file handler
        file_handler = RotatingFileHandler(
            log_dir / app.config['LOG_FILE'],
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('System Control Dashboard startup')

def init_database():
    """Initialize SQLite database"""
    db_path = 'dashboard.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create clients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT,
                ip TEXT,
                connected_at TIMESTAMP,
                last_seen TIMESTAMP,
                status TEXT DEFAULT 'offline'
            )
        ''')
        
        # Create commands table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                command TEXT,
                response TEXT,
                executed_at TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Create files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                filename TEXT,
                filepath TEXT,
                size INTEGER,
                uploaded_at TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Database initialization error: {e}")

def main():
    """Main application entry point"""
    # Validate configuration
    errors = validate_config()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Create application
    app, socketio = create_app()
    
    # Get configuration
    config = get_config()
    
    # Print startup info
    print("🚀 System Control Dashboard")
    print(f"📊 Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"🌐 Host: {config.HOST}")
    print(f"🔌 Port: {config.PORT}")
    print(f"🛡️ Debug: {config.DEBUG}")
    print("=" * 50)
    
    # Start server
    try:
        socketio.run(
            app,
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=False  # Disable reloader for production
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

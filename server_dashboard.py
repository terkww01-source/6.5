#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- باید اولین import ها همین‌ها باشند:
from gevent import monkey
monkey.patch_all()

import os
import sys
import json
import time
import logging
import sqlite3
import zipfile
import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import uuid
import threading
from urllib.parse import urlparse, parse_qs

# Web framework imports
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room, leave_room, Namespace
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Configuration
CONFIG = {
    "SECRET_KEY": os.environ.get("SECRET_KEY", "your-secret-key-change-this"),
    "DATABASE_PATH": "dashboard.db",
    "UPLOAD_FOLDER": "uploads",
    "MAX_CONTENT_LENGTH": 500 * 1024 * 1024,  # 500MB
    "PORT": int(os.environ.get("PORT", 5000)),
    "DEBUG": os.environ.get("FLASK_ENV") == "development",
    "ADMIN_USERNAME": os.environ.get("ADMIN_USERNAME", "admin"),
    "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD", "admin123"),
    "AGENT_TOKEN": os.environ.get("AGENT_TOKEN", "your-secure-agent-token-here"),
    "SESSION_TIMEOUT": 3600,  # 1 hour
    "CLIENT_TIMEOUT": 300,  # 5 minutes
    "MAX_CLIENTS": 100,
    "BACKUP_RETENTION_DAYS": 30,
    "LOG_RETENTION_DAYS": 7
}

# Setup logging
logging.basicConfig(
    level=logging.INFO if not CONFIG["DEBUG"] else logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = CONFIG["SECRET_KEY"]
app.config['MAX_CONTENT_LENGTH'] = CONFIG["MAX_CONTENT_LENGTH"]
app.config['UPLOAD_FOLDER'] = CONFIG["UPLOAD_FOLDER"]

# SocketIO setup with namespaces (بدون async_mode دستی؛ gevent خودش هندل می‌کند)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25
)

# Create upload folder
os.makedirs(CONFIG["UPLOAD_FOLDER"], exist_ok=True)

class DatabaseManager:
    """Database manager for storing client data and backups"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or CONFIG["DATABASE_PATH"]
        self.init_database()

    def init_database(self):
        """Initialize database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clients table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS clients (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        hostname TEXT,
                        os_info TEXT,
                        arch TEXT,
                        python_version TEXT,
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'offline',
                        system_info TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Backup data table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS backups (
                        id TEXT PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        backup_type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'in_progress',
                        size INTEGER DEFAULT 0,
                        file_count INTEGER DEFAULT 0,
                        metadata TEXT,
                        file_paths TEXT,
                        error_message TEXT,
                        FOREIGN KEY (client_id) REFERENCES clients (id)
                    )
                ''')
                
                # Commands table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS commands (
                        id TEXT PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        command_type TEXT NOT NULL,
                        command_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        executed_at TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        result TEXT,
                        error TEXT,
                        FOREIGN KEY (client_id) REFERENCES clients (id)
                    )
                ''')
                
                # Files table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS files (
                        id TEXT PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        backup_id TEXT,
                        original_path TEXT NOT NULL,
                        stored_path TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        file_size INTEGER,
                        file_hash TEXT,
                        mime_type TEXT,
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_sensitive BOOLEAN DEFAULT 0,
                        tags TEXT,
                        FOREIGN KEY (client_id) REFERENCES clients (id),
                        FOREIGN KEY (backup_id) REFERENCES backups (id)
                    )
                ''')
                
                # Logs table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id TEXT,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        category TEXT,
                        details TEXT
                    )
                ''')
                
                # User sessions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ip_address TEXT,
                        user_agent TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def register_client(self, client_info):
        """Register or update client information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO clients
                    (id, name, hostname, os_info, arch, python_version, last_seen, status, system_info)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'online', ?)
                ''', (
                    client_info.get("client_id"),
                    client_info.get("client_name", "Unknown"),
                    client_info.get("hostname", ""),
                    client_info.get("os", ""),
                    client_info.get("arch", ""),
                    client_info.get("python_version", ""),
                    json.dumps(client_info)
                ))
                conn.commit()
                logger.info(f"Client registered: {client_info.get('client_id')}")
        except Exception as e:
            logger.error(f"Error registering client: {e}")

    def update_client_status(self, client_id, status, system_status=None):
        """Update client status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                update_data = [status, client_id]
                query = "UPDATE clients SET status = ?, last_seen = CURRENT_TIMESTAMP"
                
                if system_status:
                    query += ", system_info = ?"
                    update_data.insert(-1, json.dumps(system_status))
                
                query += " WHERE id = ?"
                cursor.execute(query, update_data)
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating client status: {e}")

    def get_clients(self, active_only=False):
        """Get all clients"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM clients"
                if active_only:
                    query += " WHERE is_active = 1"
                query += " ORDER BY last_seen DESC"
                
                cursor.execute(query)
                columns = [description[0] for description in cursor.description]
                clients = []
                
                for row in cursor.fetchall():
                    client = dict(zip(columns, row))
                    # Parse JSON fields
                    if client['system_info']:
                        try:
                            client['system_info'] = json.loads(client['system_info'])
                        except:
                            client['system_info'] = {}
                    clients.append(client)
                
                return clients
        except Exception as e:
            logger.error(f"Error getting clients: {e}")
            return []

    def save_backup(self, backup_info):
        """Save backup information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO backups
                    (id, client_id, backup_type, status, size, file_count, metadata, file_paths)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    backup_info.get("backup_id"),
                    backup_info.get("client_id"),
                    backup_info.get("backup_type", "full"),
                    backup_info.get("status", "completed"),
                    backup_info.get("size", 0),
                    backup_info.get("file_count", 0),
                    json.dumps(backup_info),
                    json.dumps(backup_info.get("backup_files", []))
                ))
                conn.commit()
                logger.info(f"Backup saved: {backup_info.get('backup_id')}")
        except Exception as e:
            logger.error(f"Error saving backup: {e}")

    def get_backups(self, client_id=None, limit=50):
        """Get backup history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM backups"
                params = []
                
                if client_id:
                    query += " WHERE client_id = ?"
                    params.append(client_id)
                
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                backups = []
                
                for row in cursor.fetchall():
                    backup = dict(zip(columns, row))
                    # Parse JSON fields
                    if backup['metadata']:
                        try:
                            backup['metadata'] = json.loads(backup['metadata'])
                        except:
                            backup['metadata'] = {}
                    if backup['file_paths']:
                        try:
                            backup['file_paths'] = json.loads(backup['file_paths'])
                        except:
                            backup['file_paths'] = []
                    backups.append(backup)
                
                return backups
        except Exception as e:
            logger.error(f"Error getting backups: {e}")
            return []

    def save_command(self, command_info):
        """Save command to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO commands
                    (id, client_id, command_type, command_data, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    command_info.get("id", str(uuid.uuid4())),
                    command_info.get("client_id"),
                    command_info.get("type"),
                    json.dumps(command_info),
                    "pending"
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving command: {e}")
            return None

    def update_command_result(self, command_id, result, status="completed", error=None):
        """Update command result"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE commands
                    SET status = ?, result = ?, error = ?, executed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, json.dumps(result) if result else None, error, command_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating command result: {e}")

    def get_commands(self, client_id=None, status=None, limit=100):
        """Get commands history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM commands WHERE 1=1"
                params = []
                
                if client_id:
                    query += " AND client_id = ?"
                    params.append(client_id)
                
                if status:
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                columns = [description[0] for description in cursor.description]
                commands = []
                
                for row in cursor.fetchall():
                    command = dict(zip(columns, row))
                    # Parse JSON fields
                    if command['command_data']:
                        try:
                            command['command_data'] = json.loads(command['command_data'])
                        except:
                            command['command_data'] = {}
                    if command['result']:
                        try:
                            command['result'] = json.loads(command['result'])
                        except:
                            command['result'] = {}
                    commands.append(command)
                
                return commands
        except Exception as e:
            logger.error(f"Error getting commands: {e}")
            return []

    def save_file(self, file_info):
        """Save file information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO files
                    (id, client_id, backup_id, original_path, stored_path, filename,
                     file_size, file_hash, mime_type, is_sensitive, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_info.get("id", str(uuid.uuid4())),
                    file_info.get("client_id"),
                    file_info.get("backup_id"),
                    file_info.get("original_path"),
                    file_info.get("stored_path"),
                    file_info.get("filename"),
                    file_info.get("file_size", 0),
                    file_info.get("file_hash"),
                    file_info.get("mime_type"),
                    file_info.get("is_sensitive", False),
                    file_info.get("tags", "")
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving file info: {e}")

    def log_event(self, level, message, client_id=None, category=None, details=None):
        """Log event to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO logs (client_id, level, message, category, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (client_id, level, message, category, json.dumps(details) if details else None))
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging event: {e}")

    def cleanup_old_data(self):
        """Cleanup old data based on retention policies"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Cleanup old backups
                backup_cutoff = datetime.now() - timedelta(days=CONFIG["BACKUP_RETENTION_DAYS"])
                cursor.execute('''
                    DELETE FROM backups
                    WHERE created_at < ? AND status = 'completed'
                ''', (backup_cutoff,))
                
                # Cleanup old logs
                log_cutoff = datetime.now() - timedelta(days=CONFIG["LOG_RETENTION_DAYS"])
                cursor.execute('DELETE FROM logs WHERE timestamp < ?', (log_cutoff,))
                
                # Cleanup inactive sessions
                session_cutoff = datetime.now() - timedelta(seconds=CONFIG["SESSION_TIMEOUT"])
                cursor.execute('''
                    UPDATE user_sessions
                    SET is_active = 0
                    WHERE last_activity < ?
                ''', (session_cutoff,))
                
                conn.commit()
                logger.info("Old data cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

class ClientManager:
    """Manage connected clients"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.clients = {}
        self.client_locks = {}

    def register_client(self, client_id, socketio_sid=None):
        """Register a new client connection"""
        client_info = {
            "id": client_id,
            "socketio_sid": socketio_sid,
            "connected_at": datetime.now(),
            "last_heartbeat": datetime.now(),
            "status": "online",
            "command_queue": [],
            "pending_commands": {}
        }
        
        self.clients[client_id] = client_info
        self.client_locks[client_id] = threading.Lock()
        logger.info(f"Client registered: {client_id}")
        return client_info

    def unregister_client(self, client_id):
        """Unregister client connection"""
        if client_id in self.clients:
            del self.clients[client_id]
        if client_id in self.client_locks:
            del self.client_locks[client_id]
        
        # Update database
        self.db.update_client_status(client_id, "offline")
        logger.info(f"Client unregistered: {client_id}")

    def update_heartbeat(self, client_id, system_status=None):
        """Update client heartbeat"""
        if client_id in self.clients:
            self.clients[client_id]["last_heartbeat"] = datetime.now()
            if system_status:
                self.clients[client_id]["system_status"] = system_status
        
        # Update database
        self.db.update_client_status(client_id, "online", system_status)

    def get_client(self, client_id):
        """Get client information"""
        return self.clients.get(client_id)

    def get_all_clients(self):
        """Get all connected clients"""
        return list(self.clients.values())

    def is_client_online(self, client_id):
        """Check if client is online"""
        if client_id not in self.clients:
            return False
        
        client = self.clients[client_id]
        last_heartbeat = client["last_heartbeat"]
        timeout = timedelta(seconds=CONFIG["CLIENT_TIMEOUT"])
        return datetime.now() - last_heartbeat < timeout

    def add_command_to_queue(self, client_id, command):
        """Add command to client queue"""
        if client_id in self.clients:
            with self.client_locks.get(client_id, threading.Lock()):
                self.clients[client_id]["command_queue"].append(command)
            return True
        return False

    def get_pending_commands(self, client_id):
        """Get pending commands for client"""
        if client_id in self.clients:
            with self.client_locks.get(client_id, threading.Lock()):
                commands = self.clients[client_id]["command_queue"].copy()
                self.clients[client_id]["command_queue"].clear()
                return commands
        return []

    def cleanup_inactive_clients(self):
        """Remove inactive clients"""
        current_time = datetime.now()
        timeout = timedelta(seconds=CONFIG["CLIENT_TIMEOUT"])
        inactive_clients = []
        
        for client_id, client_info in self.clients.items():
            if current_time - client_info["last_heartbeat"] > timeout:
                inactive_clients.append(client_id)
        
        for client_id in inactive_clients:
            self.unregister_client(client_id)

# Initialize managers
db_manager = DatabaseManager()
client_manager = ClientManager(db_manager)

def check_agent_token():
    """Check if request has valid agent token"""
    token = request.headers.get('X-Agent-Token')
    return token == CONFIG['AGENT_TOKEN']

# Agent Namespace for Socket.IO
class AgentNamespace(Namespace):
    """Socket.IO namespace for agent communications"""
    
    def on_connect(self, sid, environ):
        """Handle agent connection"""
        # Check authentication token
        headers = environ.get('HTTP_X_AGENT_TOKEN')
        if headers != CONFIG['AGENT_TOKEN']:
            logger.warning(f"Agent connection rejected - invalid token from {sid}")
            return False
        
        logger.info(f"Agent connected: {sid}")
        return True

    def on_disconnect(self, sid):
        """Handle agent disconnection"""
        # Find client_id by sid and unregister
        for client_id, client_info in client_manager.clients.items():
            if client_info.get("socketio_sid") == sid:
                client_manager.unregister_client(client_id)
                socketio.emit('client_disconnected', {'client_id': client_id})
                break
        
        logger.info(f"Agent disconnected: {sid}")

    def on_client_register(self, sid, data):
        """Handle client registration"""
        try:
            client_id = data.get("client_id")
            if client_id:
                # Register client
                client_manager.register_client(client_id, socketio_sid=sid)
                db_manager.register_client(data)
                
                # Send acknowledgment
                self.emit('registration_ack', {
                    "status": "success",
                    "server_time": datetime.now().isoformat()
                }, room=sid)
                
                # Send any pending commands
                pending_commands = client_manager.get_pending_commands(client_id)
                for command in pending_commands:
                    self.emit('command', command, room=sid)
                
                # Notify web interface
                socketio.emit('client_connected', {
                    'client_id': client_id,
                    'client_info': data
                })
                
                logger.info(f"Client registered via Socket.IO: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client registration: {e}")

    def on_heartbeat(self, sid, data):
        """Handle client heartbeat"""
        try:
            client_id = data.get("client_id")
            if client_id:
                system_status = data.get("system_status")
                client_manager.update_heartbeat(client_id, system_status)
                
                # Send any pending commands
                pending_commands = client_manager.get_pending_commands(client_id)
                for command in pending_commands:
                    self.emit('command', command, room=sid)
                
                # Send heartbeat response
                self.emit('heartbeat_ack', {
                    "server_time": datetime.now().isoformat()
                }, room=sid)
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")

    def on_command_response(self, sid, data):
        """Handle command response from client"""
        try:
            command_id = data.get("command_id")
            client_id = data.get("client_id")
            result = data.get("result")
            status = data.get("status", "completed")
            error = data.get("error")
            
            # Update command in database
            db_manager.update_command_result(command_id, result, status, error)
            
            # Notify web interface
            socketio.emit('command_completed', {
                'command_id': command_id,
                'client_id': client_id,
                'result': result,
                'status': status,
                'error': error
            })
            
            logger.info(f"Command {command_id} completed for client {client_id}")
        except Exception as e:
            logger.error(f"Error handling command response: {e}")

    def send_command_to_client(self, client_id, command):
        """Send command to specific client"""
        try:
            # Find client socket
            client_info = client_manager.get_client(client_id)
            if client_info and client_info.get("socketio_sid"):
                sid = client_info["socketio_sid"]
                self.emit('command', command, room=sid)
                return True
            else:
                # Add to queue if client not connected
                client_manager.add_command_to_queue(client_id, command)
                return False
        except Exception as e:
            logger.error(f"Error sending command to {client_id}: {e}")
            return False

# Register agent namespace
agent_namespace = AgentNamespace('/agent')
socketio.on_namespace(agent_namespace)

# Authentication helper
def require_auth(f):
    """Decorator to require authentication"""
    from functools import wraps
    
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'authenticated' not in session or not session['authenticated']:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        
        # Update last activity
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    
    return decorated

# Web Routes
@app.route('/')
@require_auth
def dashboard():
    """Main dashboard page"""
    clients = db_manager.get_clients(active_only=True)
    recent_backups = db_manager.get_backups(limit=10)
    recent_commands = db_manager.get_commands(limit=20)
    
    # Get connected clients info
    connected_clients_info = []
    for client in clients:
        client_id = client['id']
        is_online = client_manager.is_client_online(client_id)
        client['is_online'] = is_online
        
        if is_online:
            client_info = client_manager.get_client(client_id)
            if client_info:
                client['last_heartbeat'] = client_info['last_heartbeat'].isoformat()
                client['connected_duration'] = str(datetime.now() - client_info['connected_at'])
        
        connected_clients_info.append(client)
    
    dashboard_stats = {
        'total_clients': len(clients),
        'online_clients': len([c for c in connected_clients_info if c.get('is_online', False)]),
        'total_backups': len(recent_backups),
        'pending_commands': len([c for c in recent_commands if c['status'] == 'pending'])
    }
    
    return render_template('dashboard.html',
                         clients=connected_clients_info,
                         recent_backups=recent_backups,
                         recent_commands=recent_commands,
                         stats=dashboard_stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == CONFIG['ADMIN_USERNAME'] and password == CONFIG['ADMIN_PASSWORD']:
            session['authenticated'] = True
            session['username'] = username
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            
            db_manager.log_event('INFO', f'User {username} logged in', category='auth')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            db_manager.log_event('WARNING', f'Failed login attempt for {username}', category='auth')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    username = session.get('username', 'unknown')
    session.clear()
    db_manager.log_event('INFO', f'User {username} logged out', category='auth')
    return redirect(url_for('login'))

@app.route('/clients')
@require_auth
def clients_page():
    """Clients management page"""
    clients = db_manager.get_clients()
    # Add online status
    for client in clients:
        client['is_online'] = client_manager.is_client_online(client['id'])
    
    return render_template('clients.html', clients=clients)

@app.route('/client/<client_id>')
@require_auth
def client_detail(client_id):
    """Client detail page"""
    clients = db_manager.get_clients()
    client = next((c for c in clients if c['id'] == client_id), None)
    
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('clients_page'))
    
    client['is_online'] = client_manager.is_client_online(client_id)
    backups = db_manager.get_backups(client_id=client_id)
    commands = db_manager.get_commands(client_id=client_id, limit=50)
    
    return render_template('client_detail.html',
                         client=client,
                         backups=backups,
                         commands=commands)

@app.route('/backups')
@require_auth
def backups_page():
    """Backups page"""
    client_id = request.args.get('client_id')
    backups = db_manager.get_backups(client_id=client_id, limit=100)
    clients = db_manager.get_clients()
    
    return render_template('backups.html',
                         backups=backups,
                         clients=clients,
                         selected_client=client_id)

@app.route('/commands')
@require_auth
def commands_page():
    """Commands page"""
    client_id = request.args.get('client_id')
    status = request.args.get('status')
    commands = db_manager.get_commands(client_id=client_id, status=status, limit=100)
    clients = db_manager.get_clients()
    
    return render_template('commands.html',
                         commands=commands,
                         clients=clients,
                         selected_client=client_id,
                         selected_status=status)

# API Routes
@app.route('/api/clients')
@require_auth
def api_clients():
    """API: Get all clients"""
    clients = db_manager.get_clients()
    # Add online status and connection info
    for client in clients:
        client_id = client['id']
        client['is_online'] = client_manager.is_client_online(client_id)
        
        if client['is_online']:
            client_info = client_manager.get_client(client_id)
            if client_info:
                client['connection_info'] = {
                    'connected_at': client_info['connected_at'].isoformat(),
                    'last_heartbeat': client_info['last_heartbeat'].isoformat()
                }
    
    return jsonify(clients)

@app.route('/api/client/<client_id>/command', methods=['POST'])
@require_auth
def api_send_command(client_id):
    """API: Send command to client"""
    try:
        command_data = request.json
        command_id = str(uuid.uuid4())
        
        command = {
            "id": command_id,
            "type": command_data.get("type"),
            "client_id": client_id,
            **command_data
        }
        
        # Save command to database
        db_manager.save_command(command)
        
        # Try to send via Socket.IO first
        success = agent_namespace.send_command_to_client(client_id, command)
        
        if not success:
            # Add to command queue as fallback
            client_manager.add_command_to_queue(client_id, command)
        
        db_manager.log_event('INFO', f'Command {command["type"]} sent to client {client_id}',
                           client_id=client_id, category='command')
        
        return jsonify({
            "status": "success",
            "command_id": command_id,
            "message": "Command sent successfully"
        })
        
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/client/<client_id>/backup', methods=['POST'])
@require_auth
def api_create_backup(client_id):
    """API: Create backup for client"""
    try:
        backup_type = request.json.get("backup_type", "full") if request.json else "full"
        upload_to_server = request.json.get("upload", True) if request.json else True
        
        command = {
            "type": "create_backup",
            "backup_type": backup_type,
            "upload": upload_to_server
        }
        
        command_id = str(uuid.uuid4())
        full_command = {
            "id": command_id,
            "client_id": client_id,
            **command
        }
        
        # Save command to database
        db_manager.save_command(full_command)
        
        # Send command to client
        success = agent_namespace.send_command_to_client(client_id, full_command)
        
        if not success:
            client_manager.add_command_to_queue(client_id, full_command)
        
        return jsonify({
            "status": "success",
            "command_id": command_id,
            "message": "Backup command sent successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def api_upload_file():
    """API: Upload file from client - WITH AUTHENTICATION"""
    # Check agent token
    if not check_agent_token():
        return jsonify({"error": "Unauthorized - Invalid agent token"}), 401
    
    try:
        upload_data = request.json
        client_id = upload_data.get("client_id")
        file_name = upload_data.get("file_name")
        file_data = upload_data.get("file_data")  # Base64 encoded
        
        if not all([client_id, file_name, file_data]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Decode file data
        try:
            decoded_data = base64.b64decode(file_data)
        except Exception as e:
            return jsonify({"error": "Invalid base64 data"}), 400
        
        # Create upload directory
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], client_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = secure_filename(file_name)
        stored_filename = f"{timestamp}_{safe_filename}"
        file_path = os.path.join(upload_dir, stored_filename)
        
        # Write file
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        # Calculate file hash
        file_hash = hashlib.sha256(decoded_data).hexdigest()
        
        # Save file info to database
        file_info = {
            "client_id": client_id,
            "original_path": upload_data.get("file_path", ""),
            "stored_path": file_path,
            "filename": file_name,
            "file_size": len(decoded_data),
            "file_hash": file_hash,
            "mime_type": upload_data.get("mime_type", "")
        }
        db_manager.save_file(file_info)
        
        logger.info(f"File uploaded: {file_name} from client {client_id}")
        
        return jsonify({
            "status": "success",
            "file_path": file_path,
            "file_size": len(decoded_data),
            "file_hash": file_hash
        })
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/<path:file_path>')
@require_auth
def api_download_file(file_path):
    """API: Download file"""
    try:
        # Security: ensure file is in upload folder
        full_path = os.path.abspath(file_path)
        upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        
        if not full_path.startswith(upload_folder):
            return jsonify({"error": "Access denied"}), 403
        
        if not os.path.exists(full_path):
            return jsonify({"error": "File not found"}), 404
        
        return send_file(full_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
@require_auth
def api_stats():
    """API: Get dashboard statistics"""
    try:
        clients = db_manager.get_clients()
        backups = db_manager.get_backups(limit=1000)
        commands = db_manager.get_commands(limit=1000)
        
        online_clients = [c for c in clients if client_manager.is_client_online(c['id'])]
        
        # Calculate statistics
        stats = {
            "clients": {
                "total": len(clients),
                "online": len(online_clients),
                "offline": len(clients) - len(online_clients)
            },
            "backups": {
                "total": len(backups),
                "completed": len([b for b in backups if b['status'] == 'completed']),
                "failed": len([b for b in backups if b['status'] == 'failed']),
                "in_progress": len([b for b in backups if b['status'] == 'in_progress'])
            },
            "commands": {
                "total": len(commands),
                "pending": len([c for c in commands if c['status'] == 'pending']),
                "completed": len([c for c in commands if c['status'] == 'completed']),
                "failed": len([c for c in commands if c['status'] == 'failed'])
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

# SocketIO Events for web interface
@socketio.on('connect')
def handle_connect():
    """Handle SocketIO connection from web interface"""
    if 'authenticated' not in session or not session['authenticated']:
        return False
    
    logger.info(f"Web client connected: {request.sid}")
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle SocketIO disconnection from web interface"""
    logger.info(f"Web client disconnected: {request.sid}")

@socketio.on('join_client_room')
def handle_join_client_room(data):
    """Join room for specific client updates"""
    if 'authenticated' not in session or not session['authenticated']:
        return
    
    client_id = data.get('client_id')
    if client_id:
        join_room(f"client_{client_id}")
        emit('joined_room', {'client_id': client_id})

@socketio.on('leave_client_room')
def handle_leave_client_room(data):
    """Leave client room"""
    if 'authenticated' not in session or not session['authenticated']:
        return
    
    client_id = data.get('client_id')
    if client_id:
        leave_room(f"client_{client_id}")
        emit('left_room', {'client_id': client_id})

# Background tasks
def cleanup_task():
    """Background cleanup task"""
    while True:
        try:
            # Cleanup inactive clients
            client_manager.cleanup_inactive_clients()
            
            # Cleanup old data
            db_manager.cleanup_old_data()
            
            logger.info("Cleanup task completed")
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
        
        # Sleep for 5 minutes
        time.sleep(300)

# HTML Templates (embedded for simplicity)
@app.route('/templates/base.html')
def template_base():
    """Base template"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}System Control Dashboard{% endblock %}</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .sidebar { background-color: #343a40; min-height: 100vh; }
        .sidebar .nav-link { color: #fff; }
        .sidebar .nav-link:hover { background-color: #495057; }
        .sidebar .nav-link.active { background-color: #007bff; }
        .status-online { color: #28a745; }
        .status-offline { color: #dc3545; }
        .card-stats { border-left: 4px solid #007bff; }
        .table-responsive { max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <nav class="col-md-2 col-lg-2 sidebar">
                <div class="position-sticky pt-3">
                    <h5 class="text-white mb-3">Control Panel</h5>
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link" href="/">
                                <i class="fas fa-tachometer-alt"></i> Dashboard
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/clients">
                                <i class="fas fa-desktop"></i> Clients
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/backups">
                                <i class="fas fa-download"></i> Backups
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/commands">
                                <i class="fas fa-terminal"></i> Commands
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/logout">
                                <i class="fas fa-sign-out-alt"></i> Logout
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>
            <main class="col-md-10 ms-sm-auto col-lg-10 px-md-4">
                <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                    <h1 class="h2">{% block header %}Dashboard{% endblock %}</h1>
                </div>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                {% block content %}{% endblock %}
            </main>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>'''

# Simple template rendering function
def render_simple_template(template_name, **context):
    """Render simple template with context"""
    if template_name == 'login.html':
        return f'''<!DOCTYPE html>
<html>
<head>
    <title>Login - System Control</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container">
        <div class="row justify-content-center mt-5">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h4 class="mb-0">System Control Login</h4>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Username</label>
                                <input type="text" class="form-control" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Password</label>
                                <input type="password" class="form-control" name="password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Login</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>'''
    
    elif template_name == 'dashboard.html':
        clients = context.get('clients', [])
        stats = context.get('stats', {})
        
        clients_html = ""
        for client in clients[:10]:  # Show first 10
            status = "online" if client.get('is_online') else "offline"
            status_class = "success" if status == "online" else "danger"
            clients_html += f'''
            <tr>
                <td>{client.get('name', 'Unknown')}</td>
                <td>{client.get('hostname', '')}</td>
                <td><span class="badge bg-{status_class}">{status}</span></td>
                <td>{client.get('last_seen', '')}</td>
                <td>
                    <a href="/client/{client.get('id')}" class="btn btn-sm btn-outline-primary">View</a>
                </td>
            </tr>'''
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <title>System Control Dashboard</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <span class="navbar-brand">System Control Dashboard</span>
            <div>
                <a href="/clients" class="btn btn-outline-light btn-sm me-2">Clients</a>
                <a href="/backups" class="btn btn-outline-light btn-sm me-2">Backups</a>
                <a href="/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container-fluid mt-4">
        <div class="row">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">Total Clients</h5>
                        <h2 class="text-primary">{stats.get('total_clients', 0)}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">Online Clients</h5>
                        <h2 class="text-success">{stats.get('online_clients', 0)}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">Total Backups</h5>
                        <h2 class="text-info">{stats.get('total_backups', 0)}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">Pending Commands</h5>
                        <h2 class="text-warning">{stats.get('pending_commands', 0)}</h2>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Recent Clients</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Hostname</th>
                                        <th>Status</th>
                                        <th>Last Seen</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {clients_html}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        socket.on('connect', function() {{
            console.log('Connected to server');
        }});
        
        socket.on('client_connected', function(data) {{
            location.reload(); // Simple refresh on client connect
        }});
        
        socket.on('client_disconnected', function(data) {{
            location.reload(); // Simple refresh on client disconnect
        }});
    </script>
</body>
</html>'''
    
    # Default empty template
    return "<html><body>Template not found</body></html>"

# Override render_template function for simplicity
def render_template(template_name, **context):
    """Custom render_template function"""
    return render_simple_template(template_name, **context)

# Start background cleanup task
def start_background_tasks():
    """Start background tasks"""
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

# Main application runner
def main():
    """Main application entry point"""
    # Ensure upload directory exists
    os.makedirs(CONFIG["UPLOAD_FOLDER"], exist_ok=True)
    
    # Start background tasks
    start_background_tasks()
    
    # Log startup
    logger.info(f"Starting System Control Dashboard on port {CONFIG['PORT']}")
    logger.info(f"Admin username: {CONFIG['ADMIN_USERNAME']}")
    logger.info(f"Upload folder: {CONFIG['UPLOAD_FOLDER']}")
    logger.info(f"Agent token configured: {'Yes' if CONFIG['AGENT_TOKEN'] else 'No'}")
    
    # Start the application
    socketio.run(
        app,
        host='0.0.0.0',
        port=CONFIG["PORT"],
        debug=CONFIG["DEBUG"]
    )

if __name__ == "__main__":
    main()

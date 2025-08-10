#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gunicorn configuration for System Control Dashboard
Optimized for Socket.IO and real-time communication
"""
import os
import multiprocessing
import time
import signal

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
backlog = 2048

# Worker processes
# Worker class - sync for better compatibility with Python 3.13
worker_class = "sync"
# For Socket.IO applications, use eventlet worker class with single worker
# worker_class = "eventlet"
workers = 1  # Socket.IO requires single worker for proper session handling
worker_connections = 1000

# Threading (not used with eventlet, but kept for reference)
threads = 1
thread_count = 1

# Worker behavior
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 120
keepalive = 2
graceful_timeout = 30
worker_timeout = 120

# SSL/Security
forwarded_allow_ips = "*"
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "system-control-dashboard"
default_proc_name = proc_name

# Application settings
pythonpath = "."
chdir = "."

# Development vs Production settings
if os.environ.get("FLASK_ENV") == "development":
    reload = True
    reload_engine = "auto"
    reload_extra_files = [
        "server_dashboard.py",
        "client_agent.py",
        "config.py",
        "requirements.txt"
    ]
else:
    reload = False
    preload_app = True

# Memory and performance
max_worker_memory = 512 * 1024 * 1024  # 512MB per worker
worker_memory_limit = max_worker_memory

# Custom application factory
def when_ready(server):
    """Called just after the server is started."""
    server.log.info("System Control Dashboard server is ready. Accepting connections.")
    server.log.info(f"Environment: {os.environ.get('FLASK_ENV', 'production')}")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker class: {worker_class}")
    server.log.info(f"Bind: {bind}")

def worker_int(worker):
    """Called just after worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received INT or QUIT signal, shutting down gracefully.")

def pre_fork(server, worker):
    """Called just before worker processes are forked."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def post_fork(server, worker):
    """Called just after worker processes are forked."""
    server.log.info(f"Worker {worker.pid} booted")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info(f"Worker {worker.pid} initialized application")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info(f"Worker {worker.pid} received SIGABRT signal")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug(f"{req.method} {req.path}")

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    if resp.status_code >= 400:
        worker.log.warning(f"{req.method} {req.path} - {resp.status_code}")

# Error handling
def worker_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    server.log.info(f"Worker {worker.pid} exited")

# Custom error pages
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("System Control Dashboard starting...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Configuration reloaded, recycling workers...")

def on_exit(server):
    """Called just before exiting."""
    server.log.info("System Control Dashboard shutting down...")

# Environment-specific configurations
env = os.environ.get("FLASK_ENV", "production")

if env == "production":
    # Production settings
    worker_tmp_dir = "/dev/shm"  # Use memory for worker temporary files
    tmp_upload_dir = None

    # Enhanced logging for production
    capture_output = True
    enable_stdio_inheritance = True

    # Security
    limit_request_line = 4094
    limit_request_fields = 100
    limit_request_field_size = 8190

elif env == "development":
    # Development settings
    reload = True
    timeout = 0  # Disable timeout in development
    loglevel = "debug"

    # Debug friendly settings
    capture_output = False
    enable_stdio_inheritance = False

# Socket.IO specific settings
def application(environ, start_response):
    """WSGI application wrapper for Socket.IO"""
    # Import here to avoid circular imports
    from server_dashboard import app, socketio

    # Handle Socket.IO requests
    if environ.get('PATH_INFO', '').startswith('/socket.io/'):
        return socketio.wsgi_app(environ, start_response)
    else:
        return app.wsgi_app(environ, start_response)

# Health check configuration
def health_check():
    """Simple health check for the application"""
    try:
        # Import here to avoid circular imports
        from server_dashboard import db_manager

        # Test database connection
        clients = db_manager.get_clients()

        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

# Custom middleware for request handling
def pre_request_hook(worker, req):
    """Hook called before processing each request"""
    # Log slow requests
    req.start_time = time.time()

    # Security headers for all requests
    if hasattr(req, 'environ'):
        environ = req.environ

        # Add security headers
        if 'HTTP_X_FORWARDED_PROTO' in environ:
            if environ['HTTP_X_FORWARDED_PROTO'] == 'https':
                environ['wsgi.url_scheme'] = 'https'

def post_request_hook(worker, req, environ, resp):
    """Hook called after processing each request"""
    # Calculate request duration
    if hasattr(req, 'start_time'):
        duration = time.time() - req.start_time

        # Log slow requests (> 5 seconds)
        if duration > 5:
            worker.log.warning(f"Slow request: {req.method} {req.path} took {duration:.2f}s")

        # Log error responses
        if resp.status_code >= 400:
            worker.log.error(f"Error response: {req.method} {req.path} - {resp.status_code}")

# Memory monitoring
def monitor_memory(worker):
    """Monitor worker memory usage"""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        if memory_mb > 400:  # Alert if memory > 400MB
            worker.log.warning(f"High memory usage: {memory_mb:.1f}MB")

        if memory_mb > max_worker_memory / (1024 * 1024):
            worker.log.error(f"Memory limit exceeded: {memory_mb:.1f}MB")
            # Could trigger worker restart here

    except ImportError:
        pass  # psutil not available

# Socket.IO optimization
eventlet_pool_size = 1000

# Custom error handlers
def handle_error(req, client, error):
    """Handle application errors"""
    import traceback
    error_msg = f"Error handling request {req.path}: {error}"
    print(f"ERROR: {error_msg}")
    print(traceback.format_exc())

# Performance monitoring
enable_performance_monitoring = os.environ.get("ENABLE_PERFORMANCE_MONITORING", "false").lower() == "true"

if enable_performance_monitoring:
    def performance_hook(worker, req):
        """Monitor request performance"""
        req.perf_start = time.time()

    def performance_cleanup(worker, req, environ, resp):
        """Clean up performance monitoring"""
        if hasattr(req, 'perf_start'):
            duration = time.time() - req.perf_start

            # Log to performance metrics (could send to monitoring service)
            if duration > 1:  # Log requests > 1 second
                worker.log.info(f"PERF: {req.method} {req.path} {duration:.3f}s {resp.status_code}")

# Graceful shutdown handling
def graceful_shutdown(signal_number, frame):
    """Handle graceful shutdown signals"""
    print(f"Received signal {signal_number}, shutting down gracefully...")

    # Clean up resources
    try:
        from server_dashboard import db_manager, socketio

        # Close database connections
        if hasattr(db_manager, 'close'):
            db_manager.close()

        # Stop Socket.IO
        if hasattr(socketio, 'stop'):
            socketio.stop()

    except Exception as e:
        print(f"Error during graceful shutdown: {e}")

# Register signal handlers
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)

# Custom configuration validation
def validate_config():
    """Validate Gunicorn configuration"""
    errors = []

    if workers > 1 and worker_class == "eventlet":
        errors.append("Socket.IO applications should use single worker with eventlet")

    if timeout < 30:
        errors.append("Timeout should be at least 30 seconds for Socket.IO")

    if worker_connections < 100:
        errors.append("Worker connections should be at least 100 for real-time apps")

    return errors

# Log configuration on startup
def log_configuration(server):
    """Log current configuration"""
    server.log.info("=== Gunicorn Configuration ===")
    server.log.info(f"Bind: {bind}")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker Class: {worker_class}")
    server.log.info(f"Worker Connections: {worker_connections}")
    server.log.info(f"Timeout: {timeout}")
    server.log.info(f"Keepalive: {keepalive}")
    server.log.info(f"Max Requests: {max_requests}")
    server.log.info(f"Log Level: {loglevel}")
    server.log.info(f"Environment: {os.environ.get('FLASK_ENV', 'production')}")
    server.log.info("=" * 30)

# Override hooks with our custom functions
when_ready = log_configuration
pre_request = pre_request_hook if 'pre_request_hook' in locals() else pre_request
post_request = post_request_hook if 'post_request_hook' in locals() else post_request

# Additional Socket.IO specific settings
def socketio_worker_init(worker):
    """Initialize Socket.IO worker"""
    worker.log.info("Initializing Socket.IO worker...")

    # Set eventlet monkey patching
    try:
        import eventlet
        eventlet.monkey_patch()
        worker.log.info("Eventlet monkey patching applied")
    except ImportError:
        worker.log.warning("Eventlet not available")

# Override post_worker_init for Socket.IO
def custom_post_worker_init(worker):
    """Custom worker initialization"""
    # Removed socketio_worker_init call as eventlet is no longer used.
    # If Socket.IO requires specific initialization for 'sync' worker, it should be added here.

    # Original post_worker_init logic
    worker.log.info(f"Worker {worker.pid} initialized application")

    # Validate configuration
    config_errors = validate_config()
    if config_errors:
        for error in config_errors:
            worker.log.warning(f"Config warning: {error}")

post_worker_init = custom_post_worker_init

# Environment-specific optimizations
if env == "production":
    # Production optimizations
    def optimize_for_production(server):
        """Apply production optimizations"""
        server.log.info("Applying production optimizations...")

        # Set process limits
        try:
            import resource
            # Increase file descriptor limit
            resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))
            server.log.info("File descriptor limit increased")
        except:
            server.log.warning("Could not increase file descriptor limit")

    on_starting = optimize_for_production

elif env == "development":
    # Development optimizations
    def setup_development(server):
        """Setup development environment"""
        server.log.info("Setting up development environment...")
        server.log.info("Auto-reload enabled")
        server.log.info("Debug logging enabled")

    on_starting = setup_development

# Resource cleanup
def cleanup_resources():
    """Clean up resources on shutdown"""
    try:
        # Clean up temporary files
        import tempfile
        import shutil
        temp_dirs = ['/tmp/gunicorn-*', '/tmp/eventlet-*']

        for pattern in temp_dirs:
            import glob
            for temp_path in glob.glob(pattern):
                try:
                    if os.path.isdir(temp_path):
                        shutil.rmtree(temp_path)
                    else:
                        os.remove(temp_path)
                except:
                    pass

    except Exception as e:
        print(f"Error cleaning up resources: {e}")

def final_cleanup(server):
    """Final cleanup before exit"""
    server.log.info("Performing final cleanup...")
    cleanup_resources()
    server.log.info("System Control Dashboard shutdown complete")

on_exit = final_cleanup

# Custom request routing for Socket.IO
def custom_wsgi_app(environ, start_response):
    """Custom WSGI application with Socket.IO routing"""
    try:
        from server_dashboard import app, socketio

        path = environ.get('PATH_INFO', '')

        # Route Socket.IO requests
        if path.startswith('/socket.io/'):
            return socketio.wsgi_app(environ, start_response)
        else:
            return app.wsgi_app(environ, start_response)

    except Exception as e:
        # Error handling
        print(f"WSGI Error: {e}")
        import traceback
        traceback.print_exc()

        # Return 500 error
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        return [b'Internal Server Error']

# Set the application
application = custom_wsgi_app

# Final configuration check
if __name__ == "__main__":
    print("Gunicorn Configuration Check:")
    print(f"Environment: {env}")
    print(f"Workers: {workers}")
    print(f"Worker Class: {worker_class}")
    print(f"Bind: {bind}")

    errors = validate_config()
    if errors:
        print("Configuration Issues:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Configuration looks good!")
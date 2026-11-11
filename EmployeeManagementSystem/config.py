import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
base_dir = Path(__file__).resolve().parent
dotenv_path = base_dir / '.env'
if dotenv_path.exists():
    # override=True ensures Flask's debug reloader subprocess always gets
    # the correct values from .env even if empty strings are inherited from parent env
    load_dotenv(dotenv_path, override=True)

class Config:
    """Base configuration loaded from environment variables."""
    # Flask Secret Key
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ems-dev-secret-key-replace-in-production-2026')
    
    # MySQL Database Settings
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'ems_db')
    
    # Session & Security Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    
    # Application Info
    APP_NAME = "Employee Management System"
    APP_VERSION = "1.0.0"

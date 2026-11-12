import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# Search for .env in current directory, app directory, and parent directory
base_dir = Path(__file__).resolve().parent
candidates = [
    base_dir / '.env',
    base_dir.parent / '.env',
    Path.cwd() / '.env'
]

for p in candidates:
    if p.exists():
        # Do not override system/cloud environment variables already set (e.g. on Railway)
        load_dotenv(p, override=False)
        break

class Config:
    """Base configuration loaded from environment variables."""
    # Flask Secret Key
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ems-dev-secret-key-replace-in-production-2026')
    
    # Check for MySQL URL (provided automatically by Railway as MYSQL_URL or DATABASE_URL)
    _db_url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
    _url_host = None
    _url_port = None
    _url_user = None
    _url_password = None
    _url_db = None

    if _db_url and _db_url.startswith(('mysql://', 'mysql+pymysql://')):
        parsed = urlparse(_db_url)
        _url_host = parsed.hostname
        _url_port = parsed.port
        _url_user = parsed.username
        _url_password = parsed.password
        _url_db = parsed.path.lstrip('/') if parsed.path else None

    # MySQL Database Settings:
    # Intelligently resolves Railway native variables (MYSQLHOST, MYSQLUSER, etc.),
    # Railway MYSQL_URL, or custom DB_* variables, with safe local defaults.
    
    # Host
    _env_db_host = os.environ.get('DB_HOST')
    if os.environ.get('MYSQLHOST'):
        DB_HOST = os.environ.get('MYSQLHOST')
    elif _url_host:
        DB_HOST = _url_host
    elif _env_db_host:
        DB_HOST = _env_db_host
    else:
        DB_HOST = 'localhost'

    # Port
    _env_db_port = os.environ.get('DB_PORT')
    if os.environ.get('MYSQLPORT'):
        DB_PORT = int(os.environ.get('MYSQLPORT'))
    elif _url_port:
        DB_PORT = int(_url_port)
    elif _env_db_port:
        DB_PORT = int(_env_db_port)
    else:
        DB_PORT = 3306

    # User
    _env_db_user = os.environ.get('DB_USER')
    if os.environ.get('MYSQLUSER'):
        DB_USER = os.environ.get('MYSQLUSER')
    elif _url_user:
        DB_USER = _url_user
    elif _env_db_user:
        DB_USER = _env_db_user
    else:
        DB_USER = 'root'

    # Password
    _env_db_password = os.environ.get('DB_PASSWORD')
    if os.environ.get('MYSQLPASSWORD'):
        DB_PASSWORD = os.environ.get('MYSQLPASSWORD')
    elif _url_password:
        DB_PASSWORD = _url_password
    elif _env_db_password:
        DB_PASSWORD = _env_db_password
    else:
        DB_PASSWORD = ''

    # Database Name
    _env_db_name = os.environ.get('DB_NAME')
    if os.environ.get('MYSQLDATABASE'):
        DB_NAME = os.environ.get('MYSQLDATABASE')
    elif _url_db:
        DB_NAME = _url_db
    elif _env_db_name:
        DB_NAME = _env_db_name
    else:
        DB_NAME = 'ems_db'
    
    # Session & Security Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    
    # Application Info
    APP_NAME = "Employee Management System"
    APP_VERSION = "1.0.0"

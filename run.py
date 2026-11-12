"""
Employee Management System (EMS) - Application Entry Point
Can be run directly with Python or served via Gunicorn (WSGI).
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the .env file if available
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = Path(base_dir) / 'EmployeeManagementSystem' / '.env'
if not env_path.exists():
    env_path = Path(base_dir) / '.env'

if env_path.exists():
    load_dotenv(env_path, override=False)

# Add the application directory to Python path
ems_dir = os.path.join(base_dir, 'EmployeeManagementSystem')
if os.path.exists(ems_dir) and ems_dir not in sys.path:
    sys.path.insert(0, ems_dir)
elif base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import app, init_db

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print(f"[Warning] Auto database initialization skipped: {e}")

    # Port assignment from environment (Railway / Cloud standard) or fallback to 5000
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'

    print("==================================================")
    print(" Starting Employee Management System")
    print(f" Access the application at: http://127.0.0.1:{port}")
    print("==================================================")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

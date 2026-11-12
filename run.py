"""
Employee Management System (EMS) - Application Entry Point
Run this file to start the development server on http://127.0.0.1:5000
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the .env file
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = Path(base_dir) / 'EmployeeManagementSystem' / '.env'
if not env_path.exists():
    env_path = Path(base_dir) / '.env'

if env_path.exists():
    load_dotenv(env_path, override=True)

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

    print("==================================================")
    print(" Starting Employee Management System")
    print(" Access the application at: http://127.0.0.1:5000")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)

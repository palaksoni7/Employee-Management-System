import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env FIRST so Flask's debug reloader subprocess inherits correct env values
_env_path = Path(__file__).parent / 'EmployeeManagementSystem' / '.env'
load_dotenv(_env_path, override=True)

# Ensure EmployeeManagementSystem directory is in sys.path
base_dir = os.path.dirname(os.path.abspath(__file__))
ems_dir = os.path.join(base_dir, 'EmployeeManagementSystem')
if ems_dir not in sys.path:
    sys.path.insert(0, ems_dir)

from app import app, init_db

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print(f"[Warning] Auto init skipped: {e}")
        
    print("Starting Employee Management System on http://127.0.0.1:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=True)

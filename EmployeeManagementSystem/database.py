import os
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash
from config import Config

def get_db_connection(use_database=True):
    """
    Establish and return a MySQL connection.
    If use_database is False, connects without selecting the database (useful for DB creation).
    """
    try:
        conn_params = {
            'host': Config.DB_HOST,
            'port': Config.DB_PORT,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
        }
        if use_database:
            conn_params['database'] = Config.DB_NAME

        connection = mysql.connector.connect(**conn_params)
        return connection
    except Error as e:
        print(f"[Database Error] Failed to connect to MySQL: {e}")
        raise e

def test_connection():
    """
    Test database connectivity and return status tuple: (bool, message).
    """
    try:
        conn = get_db_connection(use_database=False)
        if conn.is_connected():
            server_info = conn.get_server_info()
            conn.close()
            return True, f"Successfully connected to MySQL Server (v{server_info})"
        return False, "Failed to connect to MySQL Server"
    except Error as e:
        return False, str(e)

def query_db(query, args=(), one=False, commit=False):
    """
    Execute a parameterized SQL query safely.
    
    Parameters:
        query (str): SQL query string with %s placeholders.
        args (tuple/list): Query parameters.
        one (bool): If True, returns a single dictionary row or None.
        commit (bool): If True, commits the transaction and returns lastrowid or rowcount.
        
    Returns:
        List of dicts, single dict, or inserted id/rowcount.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute(query, args)
        
        if commit:
            conn.commit()
            last_id = cursor.lastrowid
            affected = cursor.rowcount
            return last_id if last_id else affected
        
        if one:
            return cursor.fetchone()
        return cursor.fetchall()
    except Error as e:
        if conn and commit:
            conn.rollback()
        print(f"[Database Query Error] {e} | Query: {query}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

def init_db():
    """
    Initialize MySQL database, execute schema.sql, and seed default admin.
    """
    print("[Database] Starting database initialization...")
    try:
        # Step 1: Connect to MySQL server without database
        conn = get_db_connection(use_database=False)
        cursor = conn.cursor()
        
        # Step 2: Create database if not exists
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        cursor.close()
        conn.close()
        print(f"[Database] Database '{Config.DB_NAME}' checked/created.")

        # Step 3: Connect to the specific database
        conn = get_db_connection(use_database=True)
        cursor = conn.cursor()

        # Step 4: Read and execute schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found at: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Split schema by semicolons and execute non-empty statements
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        for stmt in statements:
            # Skip standalone USE or CREATE DATABASE commands since we already created/selected it
            if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
                continue
            cursor.execute(stmt)

        # Ensure attendance enum supports 'Leave'
        try:
            cursor.execute("ALTER TABLE attendance MODIFY COLUMN status ENUM('Present', 'Absent', 'Half Day', 'Leave', 'On Leave') NOT NULL DEFAULT 'Present'")
        except Exception:
            pass

        conn.commit()
        print("[Database] All schema tables verified/created successfully.")

        # Step 5: Seed default departments if none exist
        cursor.execute("SELECT COUNT(*) AS count FROM departments")
        dept_count = cursor.fetchone()[0]
        if dept_count == 0:
            default_departments = [
                ('Human Resources', 'HR management, hiring, and employee relations'),
                ('Information Technology', 'Software development, infrastructure, and IT support'),
                ('Finance & Accounting', 'Financial planning, payroll, and budgeting'),
                ('Operations', 'Business operations, facilities, and administration')
            ]
            cursor.executemany(
                "INSERT INTO departments (name, description) VALUES (%s, %s)",
                default_departments
            )
            conn.commit()
            print("[Database] Seeded initial default departments.")

        # Step 6: Seed default admin user if none exists
        cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        admin_exists = cursor.fetchone()
        if not admin_exists:
            hashed_pw = generate_password_hash('Admin@123')
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, %s, %s)
                """,
                ('admin', 'admin@ems.com', hashed_pw, 'admin', True)
            )
            admin_user_id = cursor.lastrowid

            # Seed an employee record for the admin
            cursor.execute("SELECT id FROM departments WHERE name = 'Human Resources' LIMIT 1")
            hr_dept = cursor.fetchone()
            hr_dept_id = hr_dept[0] if hr_dept else None

            cursor.execute(
                """
                INSERT INTO employees (
                    user_id, employee_code, first_name, last_name, 
                    phone, gender, department_id, designation, 
                    date_of_joining, basic_salary
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURDATE(), %s)
                """,
                (admin_user_id, 'EMS-ADMIN-01', 'System', 'Administrator', 
                 '9876543210', 'Other', hr_dept_id, 'HR Administrator', 85000.00)
            )
            conn.commit()
            print("[Database] Seeded default admin account (username: admin / password: Admin@123).")

        # Step 7: Seed demo employees (idempotently - only if each code does not exist)
        demo_employees_seed = [
            ('EMS101', 'emp_john', 'john.doe@ems.com', 'John', 'Doe', '9876543211', 'Male', 'Information Technology', 'Junior Software Engineer', '2024-01-15', 45000.00),
            ('EMS102', 'emp_priya', 'priya.sharma@ems.com', 'Priya', 'Sharma', '9876543212', 'Female', 'Human Resources', 'HR Operations Specialist', '2024-04-10', 52000.00),
            ('EMS103', 'emp_rahul', 'rahul.verma@ems.com', 'Rahul', 'Verma', '9876543213', 'Male', 'Information Technology', 'Senior Python Backend Developer', '2023-11-15', 68000.00),
            ('EMS104', 'emp_ananya', 'ananya.patel@ems.com', 'Ananya', 'Patel', '9876543214', 'Female', 'Finance & Accounting', 'Senior Financial Analyst', '2024-01-20', 60000.00)
        ]

        for code, uname, email, fname, lname, phone, gender, dept_name, desig, doj, salary in demo_employees_seed:
            cursor.execute("SELECT id FROM employees WHERE employee_code = %s", (code,))
            if not cursor.fetchone():
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                existing_u = cursor.fetchone()
                if existing_u:
                    u_id = existing_u[0]
                else:
                    emp_pw = generate_password_hash('Password@123')
                    cursor.execute(
                        """
                        INSERT INTO users (username, email, password_hash, role, is_active)
                        VALUES (%s, %s, %s, 'employee', 1)
                        """,
                        (uname, email, emp_pw)
                    )
                    u_id = cursor.lastrowid

                cursor.execute("SELECT id FROM departments WHERE name = %s LIMIT 1", (dept_name,))
                d_row = cursor.fetchone()
                dept_id = d_row[0] if d_row else None

                cursor.execute(
                    """
                    INSERT INTO employees (
                        user_id, employee_code, first_name, last_name, 
                        phone, gender, department_id, designation, 
                        date_of_joining, basic_salary
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (u_id, code, fname, lname, phone, gender, dept_id, desig, doj, salary)
                )
                conn.commit()
                print(f"[Database] Seeded demo employee {code} ({fname} {lname}).")

        cursor.close()
        conn.close()
        print("[Database] Initialization completed successfully.")
        return True, "Database initialized successfully"
    except Error as e:
        print(f"[Database Init Error] {e}")
        return False, str(e)

"""
Authentication Module - Employee Management System
Handles Admin Login, Employee Login, Logout, and Route Protection Decorators.
"""

from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database import query_db

# Create the authentication blueprint
auth_bp = Blueprint('auth', __name__)

# =====================================================================
# ROUTE PROTECTION DECORATORS (Role-Based Access Control)
# =====================================================================

def login_required(f):
    """
    Decorator: Ensures a user is logged in before accessing a page.
    If not logged in, redirects to the login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorator: Ensures only Admin users can access administrative pages.
    If an employee tries to access an admin page, access is denied.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Access restricted to administrators only.', 'danger')
            return redirect(url_for('employee.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    """
    Decorator: Ensures only Employee users can access employee self-service pages.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'employee':
            flash('This section is reserved for employees.', 'info')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# =====================================================================
# 1. LOGIN PAGE (GET)
# =====================================================================

@auth_bp.route('/login', methods=['GET'])
def login():
    """
    Displays the login page with two options:
    1. Admin Login tab
    2. Employee Login tab
    """
    # If already logged in, redirect straight to the appropriate dashboard
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('employee.dashboard'))

    # Which tab to show active ('admin' or 'employee')
    active_tab = request.args.get('tab', 'admin')
    return render_template('auth/login.html', active_tab=active_tab)


# =====================================================================
# 2. ADMIN LOGIN (POST)
# =====================================================================

@auth_bp.route('/admin-login', methods=['POST'])
def admin_login():
    """
    Handles Admin login using username and password.
    Validates against MySQL users table where role = 'admin'.
    """
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    # Step 1: Basic form validation
    if not username or not password:
        flash('Please enter both your admin username and password.', 'danger')
        return redirect(url_for('auth.login', tab='admin'))

    try:
        # Step 2: Query the database using parameterized SQL (%s prevents SQL injection)
        user = query_db(
            "SELECT * FROM users WHERE username = %s AND role = 'admin' LIMIT 1",
            (username,),
            one=True
        )

        # Step 3: Check if admin exists and verify password hash
        if user and check_password_hash(user['password_hash'], password):
            # Check if account is active
            if not user.get('is_active', True):
                flash('This admin account has been deactivated.', 'danger')
                return redirect(url_for('auth.login', tab='admin'))

            # Step 4: Store admin details in Flask session
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['role'] = 'admin'
            session['full_name'] = 'System Administrator'

            flash(f"Welcome back, {user['username']}! Logged in as Administrator.", 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin username or password. Please try again.', 'danger')
            return redirect(url_for('auth.login', tab='admin'))

    except Exception as e:
        flash(f"Database error during admin login: {str(e)}", 'danger')
        return redirect(url_for('auth.login', tab='admin'))


# =====================================================================
# 3. EMPLOYEE LOGIN (POST)
# =====================================================================

@auth_bp.route('/employee-login', methods=['POST'])
def employee_login():
    """
    Handles Employee login using Employee ID (e.g. EMS101) or Email, and password.
    Validates against MySQL users and employees tables where role = 'employee'.
    """
    login_id = request.form.get('login_id', '').strip()
    password = request.form.get('password', '').strip()

    # Step 1: Basic form validation
    if not login_id or not password:
        flash('Please enter your Employee ID or Email and password.', 'danger')
        return redirect(url_for('auth.login', tab='employee'))

    try:
        # Step 2: Query matching employee by employee_code OR email
        query = """
            SELECT 
                u.id AS user_id, 
                u.username, 
                u.email, 
                u.password_hash, 
                u.role, 
                u.is_active,
                e.id AS employee_id, 
                e.employee_code, 
                e.first_name, 
                e.last_name, 
                e.designation
            FROM users u
            LEFT JOIN employees e ON u.id = e.user_id
            WHERE (e.employee_code = %s OR u.email = %s)
              AND u.role = 'employee'
            LIMIT 1
        """
        user = query_db(query, (login_id, login_id), one=True)

        # Step 3: Verify employee exists and check password hash
        if user and check_password_hash(user['password_hash'], password):
            # Check if active
            if not user.get('is_active', True):
                flash('Your employee account has been deactivated. Contact HR.', 'danger')
                return redirect(url_for('auth.login', tab='employee'))

            # Step 4: Store employee details in Flask session
            session.clear()
            session['user_id'] = user['user_id']
            session['employee_id'] = user['employee_id']
            session['employee_code'] = user['employee_code'] if user['employee_code'] else 'EMP'
            session['username'] = user['username']
            session['email'] = user['email']
            session['role'] = 'employee'
            
            # Set display name
            if user.get('first_name'):
                session['full_name'] = f"{user['first_name']} {user['last_name']}"
            else:
                session['full_name'] = user['username']

            flash(f"Welcome back, {session['full_name']}!", 'success')
            return redirect(url_for('employee.dashboard'))
        else:
            flash('Invalid Employee ID/Email or password. Please try again.', 'danger')
            return redirect(url_for('auth.login', tab='employee'))

    except Exception as e:
        flash(f"Database error during employee login: {str(e)}", 'danger')
        return redirect(url_for('auth.login', tab='employee'))


# =====================================================================
# 4. LOGOUT
# =====================================================================

@auth_bp.route('/logout')
def logout():
    """
    Clears the Flask session and logs the user out.
    """
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

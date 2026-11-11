"""
Admin Routes Module - Employee Management System
Handles:
1. Admin Dashboard
2. Department Management (CRUD)
3. Employee Management (CRUD)
4. Attendance Management (Daily & Monthly)
5. Leave Management (Approve/Reject & Sync Attendance)
6. Salary & Payroll Management (List, Generate, View Slip, PDF Download, Delete)
"""

import os
import math
import calendar
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from routes.auth import admin_required
from database import query_db, get_db_connection
from utils.pdf_generator import generate_payslip_pdf

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    """Check if uploaded file has a valid image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =====================================================================
# 1. ADMIN DASHBOARD
# =====================================================================

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """
    Displays the Admin Dashboard with real-time MySQL statistics,
    a department distribution chart (Chart.js), and recent activities.
    """
    metrics = {
        'total_employees': 0,
        'active_employees': 0,
        'total_departments': 0,
        'today_present': 0,
        'on_leave_today': 0
    }
    chart_labels = []
    chart_counts = []
    recent_employees = []
    recent_leaves = []

    try:
        # 1. Total Employees
        res_emp = query_db("SELECT COUNT(*) AS total FROM employees", one=True)
        if res_emp:
            metrics['total_employees'] = res_emp['total']

        # 2. Active Employees
        res_active = query_db(
            "SELECT COUNT(*) AS total FROM users WHERE role = 'employee' AND is_active = 1",
            one=True
        )
        if res_active:
            metrics['active_employees'] = res_active['total']

        # 3. Total Departments
        res_dept = query_db("SELECT COUNT(*) AS total FROM departments", one=True)
        if res_dept:
            metrics['total_departments'] = res_dept['total']

        # 4. Employees Present Today
        res_att = query_db(
            "SELECT COUNT(*) AS total FROM attendance WHERE date = CURDATE() AND status = 'Present'",
            one=True
        )
        if res_att:
            metrics['today_present'] = res_att['total']

        # 5. Employees on Approved Leave Today
        res_leave = query_db(
            """
            SELECT COUNT(*) AS total FROM leave_requests 
            WHERE status = 'Approved' AND CURDATE() BETWEEN start_date AND end_date
            """,
            one=True
        )
        if res_leave:
            metrics['on_leave_today'] = res_leave['total']

        # 6. Department-wise employee counts for Chart.js
        dept_data = query_db(
            """
            SELECT d.name, COUNT(e.id) AS emp_count 
            FROM departments d 
            LEFT JOIN employees e ON d.id = e.department_id 
            GROUP BY d.id, d.name
            ORDER BY d.name ASC
            """
        )
        for row in dept_data:
            chart_labels.append(row['name'])
            chart_counts.append(row['emp_count'])

        # 7. Recent Enrolled Employees
        recent_employees = query_db(
            """
            SELECT e.id, e.employee_code, e.first_name, e.last_name, e.designation, 
                   e.date_of_joining, d.name AS department_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.id
            ORDER BY e.created_at DESC
            LIMIT 5
            """
        )

        # 8. Recent Leave Applications
        recent_leaves = query_db(
            """
            SELECT lr.id, lr.leave_type, lr.start_date, lr.end_date, lr.status, lr.applied_at,
                   e.first_name, e.last_name, e.employee_code
            FROM leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            ORDER BY lr.applied_at DESC
            LIMIT 5
            """
        )

    except Exception as e:
        flash(f"Error loading dashboard statistics: {str(e)}", "danger")

    return render_template(
        'admin/dashboard.html',
        metrics=metrics,
        chart_labels=chart_labels,
        chart_counts=chart_counts,
        recent_employees=recent_employees,
        recent_leaves=recent_leaves
    )


# =====================================================================
# 2. DEPARTMENT MANAGEMENT (CRUD)
# =====================================================================

@admin_bp.route('/departments')
@admin_required
def departments():
    """Displays the list of all departments with employee counts."""
    depts = []
    try:
        query = """
            SELECT d.id, d.name, d.description, d.created_at,
                   COUNT(e.id) AS employee_count
            FROM departments d
            LEFT JOIN employees e ON d.id = e.department_id
            GROUP BY d.id, d.name, d.description, d.created_at
            ORDER BY d.id DESC
        """
        depts = query_db(query)
    except Exception as e:
        flash(f"Error loading departments: {str(e)}", "danger")

    return render_template('admin/departments.html', departments=depts)


@admin_bp.route('/departments/add', methods=['POST'])
@admin_required
def add_department():
    """Adds a new department to MySQL."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash("Department name is required.", "danger")
        return redirect(url_for('admin.departments'))

    try:
        existing = query_db("SELECT id FROM departments WHERE name = %s", (name,), one=True)
        if existing:
            flash(f"Department '{name}' already exists.", "warning")
            return redirect(url_for('admin.departments'))

        query_db(
            "INSERT INTO departments (name, description) VALUES (%s, %s)",
            (name, description),
            commit=True
        )
        flash(f"Department '{name}' created successfully!", "success")
    except Exception as e:
        flash(f"Failed to create department: {str(e)}", "danger")

    return redirect(url_for('admin.departments'))


@admin_bp.route('/departments/edit/<int:dept_id>', methods=['POST'])
@admin_required
def edit_department(dept_id):
    """Updates an existing department's name and description."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash("Department name cannot be empty.", "danger")
        return redirect(url_for('admin.departments'))

    try:
        existing = query_db(
            "SELECT id FROM departments WHERE name = %s AND id != %s",
            (name, dept_id),
            one=True
        )
        if existing:
            flash(f"Another department with name '{name}' already exists.", "warning")
            return redirect(url_for('admin.departments'))

        query_db(
            "UPDATE departments SET name = %s, description = %s WHERE id = %s",
            (name, description, dept_id),
            commit=True
        )
        flash("Department updated successfully!", "success")
    except Exception as e:
        flash(f"Failed to update department: {str(e)}", "danger")

    return redirect(url_for('admin.departments'))


@admin_bp.route('/departments/delete/<int:dept_id>', methods=['POST'])
@admin_required
def delete_department(dept_id):
    """Safely deletes a department if no employees are currently assigned to it."""
    try:
        emp_check = query_db(
            "SELECT COUNT(*) AS total FROM employees WHERE department_id = %s",
            (dept_id,),
            one=True
        )
        if emp_check and emp_check['total'] > 0:
            flash(
                f"Cannot delete department. There are {emp_check['total']} employee(s) assigned to it. "
                "Please reassign or delete them first.",
                "warning"
            )
            return redirect(url_for('admin.departments'))

        query_db("DELETE FROM departments WHERE id = %s", (dept_id,), commit=True)
        flash("Department deleted successfully.", "success")
    except Exception as e:
        flash(f"Failed to delete department: {str(e)}", "danger")

    return redirect(url_for('admin.departments'))


# =====================================================================
# 3. EMPLOYEE MANAGEMENT (CRUD)
# =====================================================================

@admin_bp.route('/employees')
@admin_required
def employees():
    """Lists employees with search, department/status filters, and pagination."""
    search = request.args.get('search', '').strip()
    department_id = request.args.get('department', '').strip()
    status = request.args.get('status', '').strip()
    
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    per_page = 8
    offset = (page - 1) * per_page

    employees_list = []
    departments_list = []
    total_records = 0
    total_pages = 1

    try:
        departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")

        where_clauses = ["u.role = 'employee'"]
        params = []

        if search:
            where_clauses.append(
                "(e.employee_code LIKE %s OR e.first_name LIKE %s OR e.last_name LIKE %s OR u.email LIKE %s)"
            )
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])

        if department_id and department_id.isdigit():
            where_clauses.append("e.department_id = %s")
            params.append(int(department_id))

        if status in ['0', '1']:
            where_clauses.append("u.is_active = %s")
            params.append(int(status))

        where_sql = " WHERE " + " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(e.id) AS total
            FROM employees e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN departments d ON e.department_id = d.id
            {where_sql}
        """
        count_res = query_db(count_sql, tuple(params), one=True)
        total_records = count_res['total'] if count_res else 0
        total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1

        data_sql = f"""
            SELECT 
                e.id, e.employee_code, e.first_name, e.last_name, e.phone, e.gender,
                e.designation, e.basic_salary, e.date_of_joining, e.profile_photo,
                d.name AS department_name, 
                u.email, u.is_active
            FROM employees e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN departments d ON e.department_id = d.id
            {where_sql}
            ORDER BY e.id DESC
            LIMIT %s OFFSET %s
        """
        data_params = list(params) + [per_page, offset]
        employees_list = query_db(data_sql, tuple(data_params))

    except Exception as e:
        flash(f"Error loading employee records: {str(e)}", "danger")

    return render_template(
        'admin/employees.html',
        employees=employees_list,
        departments=departments_list,
        search=search,
        selected_dept=department_id,
        selected_status=status,
        current_page=page,
        total_pages=total_pages,
        total_records=total_records
    )


@admin_bp.route('/employees/add', methods=['GET', 'POST'])
@admin_required
def add_employee():
    """Enrolls a new employee, creates user login credentials and profile."""
    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")

    if request.method == 'POST':
        employee_code = request.form.get('employee_code', '').strip().upper()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        gender = request.form.get('gender', 'Male')
        department_id = request.form.get('department_id') or None
        designation = request.form.get('designation', '').strip()
        basic_salary = request.form.get('basic_salary', '0.00').strip()
        date_of_joining = request.form.get('date_of_joining', '').strip()
        address = request.form.get('address', '').strip()
        is_active = 1 if request.form.get('is_active') == '1' else 0

        if not employee_code or not full_name or not email or not date_of_joining:
            flash("Employee ID, Full Name, Email, and Joining Date are required.", "danger")
            return render_template('admin/add_employee.html', departments=departments_list)

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        if not password:
            password = 'Emp@123'

        try:
            # 1. Uniqueness check for Employee ID
            existing_code = query_db(
                "SELECT id FROM employees WHERE employee_code = %s",
                (employee_code,),
                one=True
            )
            if existing_code:
                flash(f"Employee ID '{employee_code}' is already assigned to another employee.", "danger")
                return render_template('admin/add_employee.html', departments=departments_list)

            # 2. Uniqueness check for Email in users table
            existing_email = query_db(
                "SELECT id FROM users WHERE email = %s",
                (email,),
                one=True
            )
            if existing_email:
                flash(f"Email '{email}' is already registered with an account.", "danger")
                return render_template('admin/add_employee.html', departments=departments_list)

            # 3. Handle optional profile photo upload
            photo_filename = 'default_avatar.png'
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename != '' and allowed_file(file.filename):
                    safe_name = secure_filename(file.filename)
                    photo_filename = f"{employee_code}_{safe_name}"
                    upload_folder = os.path.join(current_app.root_path, 'static', 'images', 'profiles')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, photo_filename))

            # 4. Insert into users and employees tables within a transaction
            conn = get_db_connection(use_database=True)
            cursor = conn.cursor(dictionary=True)
            try:
                username = f"emp_{employee_code.lower()}"
                hashed_pw = generate_password_hash(password)

                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, 'employee', %s)
                    """,
                    (username, email, hashed_pw, is_active)
                )
                user_id = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO employees (
                        user_id, employee_code, first_name, last_name, phone,
                        gender, department_id, designation, basic_salary,
                        date_of_joining, address, profile_photo
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id, employee_code, first_name, last_name, phone,
                        gender, department_id, designation, float(basic_salary or 0),
                        date_of_joining, address, photo_filename
                    )
                )
                conn.commit()
                flash(f"Employee {full_name} ({employee_code}) enrolled successfully!", "success")
                return redirect(url_for('admin.employees'))

            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
                conn.close()

        except Exception as e:
            flash(f"Error enrolling employee: {str(e)}", "danger")

    return render_template('admin/add_employee.html', departments=departments_list)


@admin_bp.route('/employees/view/<int:emp_id>')
@admin_required
def view_employee(emp_id):
    """Displays the complete Profile view for a specific employee."""
    try:
        emp = query_db(
            """
            SELECT e.*, d.name AS department_name, u.email, u.username, u.is_active
            FROM employees e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN departments d ON e.department_id = d.id
            WHERE e.id = %s
            """,
            (emp_id,),
            one=True
        )
        if not emp:
            flash("Employee not found.", "warning")
            return redirect(url_for('admin.employees'))

        recent_attendance = query_db(
            """
            SELECT date, clock_in, clock_out, status, notes
            FROM attendance
            WHERE employee_id = %s
            ORDER BY date DESC
            LIMIT 7
            """,
            (emp_id,)
        )

        recent_leaves = query_db(
            """
            SELECT leave_type, start_date, end_date, total_days, reason, status
            FROM leave_requests
            WHERE employee_id = %s
            ORDER BY applied_at DESC
            LIMIT 5
            """,
            (emp_id,)
        )

        return render_template(
            'admin/view_employee.html',
            employee=emp,
            recent_attendance=recent_attendance,
            recent_leaves=recent_leaves
        )
    except Exception as e:
        flash(f"Error loading employee profile: {str(e)}", "danger")
        return redirect(url_for('admin.employees'))


@admin_bp.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@admin_required
def edit_employee(emp_id):
    """Updates an employee profile and associated user account."""
    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")
    
    emp = query_db(
        """
        SELECT e.*, u.email, u.is_active
        FROM employees e
        JOIN users u ON e.user_id = u.id
        WHERE e.id = %s
        """,
        (emp_id,),
        one=True
    )
    if not emp:
        flash("Employee not found.", "warning")
        return redirect(url_for('admin.employees'))

    if request.method == 'POST':
        employee_code = request.form.get('employee_code', '').strip().upper()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        gender = request.form.get('gender', 'Male')
        department_id = request.form.get('department_id') or None
        designation = request.form.get('designation', '').strip()
        basic_salary = request.form.get('basic_salary', '0.00').strip()
        date_of_joining = request.form.get('date_of_joining', '').strip()
        address = request.form.get('address', '').strip()
        is_active = 1 if request.form.get('is_active') == '1' else 0

        if not employee_code or not full_name or not email or not date_of_joining:
            flash("Employee ID, Full Name, Email, and Joining Date are required.", "danger")
            return render_template('admin/edit_employee.html', employee=emp, departments=departments_list)

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        try:
            code_conflict = query_db(
                "SELECT id FROM employees WHERE employee_code = %s AND id != %s",
                (employee_code, emp_id),
                one=True
            )
            if code_conflict:
                flash(f"Employee ID '{employee_code}' is already used by another employee.", "danger")
                return render_template('admin/edit_employee.html', employee=emp, departments=departments_list)

            email_conflict = query_db(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (email, emp['user_id']),
                one=True
            )
            if email_conflict:
                flash(f"Email '{email}' is already registered with another account.", "danger")
                return render_template('admin/edit_employee.html', employee=emp, departments=departments_list)

            photo_filename = emp['profile_photo']
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename != '' and allowed_file(file.filename):
                    safe_name = secure_filename(file.filename)
                    photo_filename = f"{employee_code}_{safe_name}"
                    upload_folder = os.path.join(current_app.root_path, 'static', 'images', 'profiles')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, photo_filename))

            conn = get_db_connection(use_database=True)
            cursor = conn.cursor()
            try:
                if password:
                    hashed_pw = generate_password_hash(password)
                    cursor.execute(
                        "UPDATE users SET email = %s, password_hash = %s, is_active = %s WHERE id = %s",
                        (email, hashed_pw, is_active, emp['user_id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET email = %s, is_active = %s WHERE id = %s",
                        (email, is_active, emp['user_id'])
                    )

                cursor.execute(
                    """
                    UPDATE employees SET
                        employee_code = %s, first_name = %s, last_name = %s,
                        phone = %s, gender = %s, department_id = %s,
                        designation = %s, basic_salary = %s, date_of_joining = %s,
                        address = %s, profile_photo = %s
                    WHERE id = %s
                    """,
                    (
                        employee_code, first_name, last_name,
                        phone, gender, department_id,
                        designation, float(basic_salary or 0), date_of_joining,
                        address, photo_filename, emp_id
                    )
                )
                conn.commit()
                flash(f"Employee {first_name} {last_name} updated successfully!", "success")
                return redirect(url_for('admin.employees'))

            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
                conn.close()

        except Exception as e:
            flash(f"Error updating employee: {str(e)}", "danger")

    return render_template('admin/edit_employee.html', employee=emp, departments=departments_list)


@admin_bp.route('/employees/delete/<int:emp_id>', methods=['POST'])
@admin_required
def delete_employee(emp_id):
    """Deletes an employee and their corresponding user record."""
    try:
        emp = query_db("SELECT user_id, first_name, last_name FROM employees WHERE id = %s", (emp_id,), one=True)
        if not emp:
            flash("Employee not found.", "warning")
            return redirect(url_for('admin.employees'))

        query_db("DELETE FROM users WHERE id = %s", (emp['user_id'],), commit=True)
        flash(f"Employee {emp['first_name']} {emp['last_name']} removed successfully.", "success")
    except Exception as e:
        flash(f"Error deleting employee: {str(e)}", "danger")

    return redirect(url_for('admin.employees'))


# =====================================================================
# 4. ATTENDANCE MANAGEMENT (ADMIN)
# =====================================================================

@admin_bp.route('/attendance')
@admin_required
def attendance():
    """
    Displays daily attendance records for all active employees.
    Supports filtering by Date, Department, and Employee Search.
    """
    today_str = date.today().strftime('%Y-%m-%d')
    selected_date_str = request.args.get('date', today_str).strip() or today_str
    department_id = request.args.get('department', '').strip()
    search = request.args.get('search', '').strip()

    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")
    attendance_list = []
    stats = {'present': 0, 'absent': 0, 'half_day': 0, 'leave': 0, 'not_marked': 0, 'total': 0}

    try:
        where_clauses = ["u.role = 'employee'", "u.is_active = 1"]
        params = [selected_date_str]

        if department_id and department_id.isdigit():
            where_clauses.append("e.department_id = %s")
            params.append(int(department_id))

        if search:
            where_clauses.append("(e.employee_code LIKE %s OR e.first_name LIKE %s OR e.last_name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                e.id AS employee_id, e.employee_code, e.first_name, e.last_name, 
                e.designation, d.name AS department_name,
                a.id AS attendance_id, a.clock_in, a.clock_out, 
                COALESCE(a.status, 'Not Marked') AS status, 
                a.notes
            FROM employees e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN departments d ON e.department_id = d.id
            LEFT JOIN attendance a ON e.id = a.employee_id AND a.date = %s
            {where_sql}
            ORDER BY e.first_name ASC
        """
        attendance_list = query_db(query, tuple(params))

        stats['total'] = len(attendance_list)
        for row in attendance_list:
            st = row['status']
            if st == 'Present':
                stats['present'] += 1
            elif st == 'Absent':
                stats['absent'] += 1
            elif st == 'Half Day':
                stats['half_day'] += 1
            elif st in ['Leave', 'On Leave']:
                stats['leave'] += 1
            else:
                stats['not_marked'] += 1

    except Exception as e:
        flash(f"Error loading attendance: {str(e)}", "danger")

    return render_template(
        'admin/attendance.html',
        attendance_records=attendance_list,
        departments=departments_list,
        selected_date=selected_date_str,
        selected_dept=department_id,
        search=search,
        stats=stats
    )


@admin_bp.route('/attendance/mark', methods=['POST'])
@admin_required
def mark_attendance():
    """
    Marks or updates an employee's attendance record for a specific date.
    Prevents duplicate records using MySQL's ON DUPLICATE KEY UPDATE.
    """
    employee_id = request.form.get('employee_id')
    att_date = request.form.get('date', date.today().strftime('%Y-%m-%d')).strip()
    status = request.form.get('status', 'Present').strip()
    clock_in = request.form.get('clock_in', '').strip() or None
    clock_out = request.form.get('clock_out', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    if not employee_id or not att_date:
        flash("Employee and Date are required to mark attendance.", "danger")
        return redirect(url_for('admin.attendance', date=att_date))

    try:
        query = """
            INSERT INTO attendance (employee_id, date, status, clock_in, clock_out, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                clock_in = VALUES(clock_in),
                clock_out = VALUES(clock_out),
                notes = VALUES(notes)
        """
        query_db(query, (employee_id, att_date, status, clock_in, clock_out, notes), commit=True)
        flash("Attendance record saved successfully!", "success")
    except Exception as e:
        flash(f"Failed to record attendance: {str(e)}", "danger")

    return redirect(url_for('admin.attendance', date=att_date))


@admin_bp.route('/attendance/monthly')
@admin_required
def monthly_attendance():
    """Displays monthly attendance overview and percentages across all employees."""
    today = date.today()
    try:
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
    except ValueError:
        month = today.month
        year = today.year

    department_id = request.args.get('department', '').strip()
    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")

    monthly_summary = []
    try:
        where_clauses = ["u.role = 'employee'", "u.is_active = 1"]
        params = [month, year]

        if department_id and department_id.isdigit():
            where_clauses.append("e.department_id = %s")
            params.append(int(department_id))

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                e.id AS employee_id, e.employee_code, e.first_name, e.last_name, 
                d.name AS department_name,
                COUNT(a.id) AS total_logged,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                SUM(CASE WHEN a.status = 'Half Day' THEN 1 ELSE 0 END) AS half_day_count,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                SUM(CASE WHEN a.status IN ('Leave', 'On Leave') THEN 1 ELSE 0 END) AS leave_count
            FROM employees e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN departments d ON e.department_id = d.id
            LEFT JOIN attendance a ON e.id = a.employee_id AND MONTH(a.date) = %s AND YEAR(a.date) = %s
            {where_sql}
            GROUP BY e.id, e.employee_code, e.first_name, e.last_name, d.name
            ORDER BY e.first_name ASC
        """
        rows = query_db(query, tuple(params))

        for r in rows:
            logged = r['total_logged'] or 0
            present = r['present_count'] or 0
            half = r['half_day_count'] or 0
            pct = 0.0
            if logged > 0:
                pct = round(((present + (half * 0.5)) / logged) * 100, 1)
            
            monthly_summary.append({
                'employee_id': r['employee_id'],
                'employee_code': r['employee_code'],
                'name': f"{r['first_name']} {r['last_name']}",
                'department_name': r['department_name'] or 'Unassigned',
                'total_logged': logged,
                'present_count': present,
                'half_day_count': half,
                'absent_count': r['absent_count'] or 0,
                'leave_count': r['leave_count'] or 0,
                'percentage': pct
            })

    except Exception as e:
        flash(f"Error loading monthly summary: {str(e)}", "danger")

    month_name = calendar.month_name[month]

    return render_template(
        'admin/monthly_attendance.html',
        summary=monthly_summary,
        departments=departments_list,
        selected_month=month,
        selected_year=year,
        selected_dept=department_id,
        month_name=month_name
    )


# =====================================================================
# 5. LEAVE MANAGEMENT (ADMIN)
# =====================================================================

@admin_bp.route('/leaves')
@admin_required
def leaves():
    """Displays all employee leave requests with filters for Status and Department."""
    status_filter = request.args.get('status', 'All').strip()
    department_id = request.args.get('department', '').strip()
    search = request.args.get('search', '').strip()

    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")
    leaves_list = []
    stats = {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0}

    try:
        where_clauses = []
        params = []

        if status_filter in ['Pending', 'Approved', 'Rejected']:
            where_clauses.append("lr.status = %s")
            params.append(status_filter)

        if department_id and department_id.isdigit():
            where_clauses.append("e.department_id = %s")
            params.append(int(department_id))

        if search:
            where_clauses.append("(e.employee_code LIKE %s OR e.first_name LIKE %s OR e.last_name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
            SELECT 
                lr.*, 
                e.employee_code, e.first_name, e.last_name, e.profile_photo,
                d.name AS department_name
            FROM leave_requests lr
            JOIN employees e ON lr.employee_id = e.id
            LEFT JOIN departments d ON e.department_id = d.id
            {where_sql}
            ORDER BY lr.applied_at DESC
        """
        leaves_list = query_db(query, tuple(params))

        counts_res = query_db(
            """
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) AS rejected
            FROM leave_requests
            """,
            one=True
        )
        if counts_res:
            stats['total'] = counts_res['total'] or 0
            stats['pending'] = counts_res['pending'] or 0
            stats['approved'] = counts_res['approved'] or 0
            stats['rejected'] = counts_res['rejected'] or 0

    except Exception as e:
        flash(f"Error loading leave applications: {str(e)}", "danger")

    return render_template(
        'admin/leaves.html',
        leaves=leaves_list,
        departments=departments_list,
        selected_status=status_filter,
        selected_dept=department_id,
        search=search,
        stats=stats
    )


@admin_bp.route('/leaves/approve/<int:leave_id>', methods=['POST'])
@admin_required
def approve_leave(leave_id):
    """
    Approves a leave request.
    Crucial requirement: Automatically reflects approved leave dates
    into the attendance table with status 'Leave'.
    """
    try:
        leave = query_db("SELECT * FROM leave_requests WHERE id = %s", (leave_id,), one=True)
        if not leave:
            flash("Leave request not found.", "warning")
            return redirect(url_for('admin.leaves'))

        query_db(
            "UPDATE leave_requests SET status = 'Approved', reviewed_at = NOW() WHERE id = %s",
            (leave_id,),
            commit=True
        )

        start_date = leave['start_date']
        end_date = leave['end_date']
        current_date = start_date

        while current_date <= end_date:
            note_text = f"Approved Leave ({leave['leave_type']})"
            query_db(
                """
                INSERT INTO attendance (employee_id, date, status, notes)
                VALUES (%s, %s, 'Leave', %s)
                ON DUPLICATE KEY UPDATE status = 'Leave', notes = VALUES(notes)
                """,
                (leave['employee_id'], current_date, note_text),
                commit=True
            )
            current_date += timedelta(days=1)

        flash("Leave request approved and reflected in attendance records successfully!", "success")

    except Exception as e:
        flash(f"Error approving leave request: {str(e)}", "danger")

    return redirect(url_for('admin.leaves'))


@admin_bp.route('/leaves/reject/<int:leave_id>', methods=['POST'])
@admin_required
def reject_leave(leave_id):
    """Rejects a leave request and records rejection remarks."""
    remarks = request.form.get('admin_remarks', '').strip()
    try:
        query_db(
            """
            UPDATE leave_requests 
            SET status = 'Rejected', admin_remarks = %s, reviewed_at = NOW() 
            WHERE id = %s
            """,
            (remarks if remarks else 'Application rejected by administration.', leave_id),
            commit=True
        )
        flash("Leave request rejected.", "info")
    except Exception as e:
        flash(f"Error rejecting leave request: {str(e)}", "danger")

    return redirect(url_for('admin.leaves'))


# =====================================================================
# 6. SALARY AND PAYROLL MANAGEMENT (ADMIN)
# =====================================================================

@admin_bp.route('/payroll')
@admin_required
def payroll():
    """
    Displays the list of generated payroll records with filters for Month,
    Year, Department, and Employee Search.
    """
    today = date.today()
    try:
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
    except ValueError:
        month = today.month
        year = today.year

    department_id = request.args.get('department', '').strip()
    search = request.args.get('search', '').strip()

    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")
    payroll_records = []
    stats = {'total_records': 0, 'total_net': 0.0, 'total_allowances': 0.0, 'total_deductions': 0.0}

    try:
        where_clauses = ["p.month = %s", "p.year = %s"]
        params = [month, year]

        if department_id and department_id.isdigit():
            where_clauses.append("e.department_id = %s")
            params.append(int(department_id))

        if search:
            where_clauses.append("(e.employee_code LIKE %s OR e.first_name LIKE %s OR e.last_name LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                p.*,
                e.employee_code, e.first_name, e.last_name, e.designation,
                d.name AS department_name
            FROM payroll p
            JOIN employees e ON p.employee_id = e.id
            LEFT JOIN departments d ON e.department_id = d.id
            {where_sql}
            ORDER BY p.id DESC
        """
        payroll_records = query_db(query, tuple(params))

        stats['total_records'] = len(payroll_records)
        for rec in payroll_records:
            stats['total_net'] += float(rec['net_salary'] or 0)
            stats['total_allowances'] += float(rec['allowances'] or 0)
            stats['total_deductions'] += float(rec['deductions'] or 0)

    except Exception as e:
        flash(f"Error loading payroll records: {str(e)}", "danger")

    month_name = calendar.month_name[month]

    return render_template(
        'admin/payroll.html',
        payroll_records=payroll_records,
        departments=departments_list,
        selected_month=month,
        selected_year=year,
        selected_dept=department_id,
        search=search,
        stats=stats,
        month_name=month_name
    )


@admin_bp.route('/payroll/generate', methods=['GET', 'POST'])
@admin_required
def generate_payroll():
    """
    GET: Displays the payroll generation form.
    POST: Validates inputs, calculates net salary (Basic + Allowances - Deductions),
          prevents duplicate payroll for the same employee and month, and stores in MySQL.
    """
    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")
    employees_list = query_db(
        """
        SELECT e.id, e.employee_code, e.first_name, e.last_name, e.basic_salary, d.name AS department_name
        FROM employees e
        JOIN users u ON e.user_id = u.id
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE u.role = 'employee' AND u.is_active = 1
        ORDER BY e.first_name ASC
        """
    )

    today = date.today()
    default_month = today.month
    default_year = today.year

    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        month = int(request.form.get('month', default_month))
        year = int(request.form.get('year', default_year))
        basic_salary_str = request.form.get('basic_salary', '0').strip()
        allowances_str = request.form.get('allowances', '0').strip()
        deductions_str = request.form.get('deductions', '0').strip()
        status = request.form.get('status', 'Pending').strip()
        payment_date = request.form.get('payment_date', '').strip() or None
        payment_method = request.form.get('payment_method', 'Bank Transfer').strip()

        if not employee_id:
            flash("Please select an employee.", "danger")
            return render_template('admin/generate_payroll.html', employees=employees_list, default_month=default_month, default_year=default_year)

        try:
            basic_salary = float(basic_salary_str)
            allowances = float(allowances_str) if allowances_str else 0.0
            deductions = float(deductions_str) if deductions_str else 0.0

            if basic_salary <= 0:
                flash("Basic salary must be greater than zero.", "danger")
                return render_template('admin/generate_payroll.html', employees=employees_list, default_month=default_month, default_year=default_year)

            if allowances < 0 or deductions < 0:
                flash("Allowances and Deductions cannot be negative.", "danger")
                return render_template('admin/generate_payroll.html', employees=employees_list, default_month=default_month, default_year=default_year)

            # Calculation: Net Salary = Basic Salary + Allowances - Deductions
            net_salary = basic_salary + allowances - deductions
            if net_salary < 0:
                flash("Net salary cannot be negative. Deductions exceed gross earnings.", "danger")
                return render_template('admin/generate_payroll.html', employees=employees_list, default_month=default_month, default_year=default_year)

            # Prevent duplicate payroll generation for the same employee and month
            existing = query_db(
                "SELECT id FROM payroll WHERE employee_id = %s AND month = %s AND year = %s",
                (employee_id, month, year),
                one=True
            )
            if existing:
                flash(f"Payroll for this employee for {calendar.month_name[month]} {year} has already been generated.", "warning")
                return redirect(url_for('admin.payroll', month=month, year=year))

            # Insert into payroll
            query_db(
                """
                INSERT INTO payroll (
                    employee_id, month, year, basic_salary, allowances, deductions,
                    net_salary, status, payment_date, payment_method
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (employee_id, month, year, basic_salary, allowances, deductions, net_salary, status, payment_date, payment_method),
                commit=True
            )

            # Update base salary on employee record if changed
            query_db("UPDATE employees SET basic_salary = %s WHERE id = %s", (basic_salary, employee_id), commit=True)

            flash("Payroll generated successfully!", "success")
            return redirect(url_for('admin.payroll', month=month, year=year))

        except ValueError:
            flash("Invalid numeric value entered for salary, allowances, or deductions.", "danger")
        except Exception as e:
            flash(f"Failed to generate payroll: {str(e)}", "danger")

    return render_template(
        'admin/generate_payroll.html',
        employees=employees_list,
        default_month=default_month,
        default_year=default_year
    )


@admin_bp.route('/payroll/slip/<int:payroll_id>')
@admin_required
def view_payslip(payroll_id):
    """Displays the web-based printable salary slip for an employee."""
    query = """
        SELECT 
            p.*, 
            e.employee_code, e.first_name, e.last_name, e.designation, e.phone,
            d.name AS department_name,
            u.email
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        LEFT JOIN departments d ON e.department_id = d.id
        JOIN users u ON e.user_id = u.id
        WHERE p.id = %s
    """
    record = query_db(query, (payroll_id,), one=True)
    if not record:
        flash("Salary slip not found.", "warning")
        return redirect(url_for('admin.payroll'))

    month_name = calendar.month_name[record['month']]
    return render_template('admin/payslip.html', slip=record, month_name=month_name)


@admin_bp.route('/payroll/pdf/<int:payroll_id>')
@admin_required
def download_payslip_pdf(payroll_id):
    """Generates and downloads the professional PDF salary slip."""
    query = """
        SELECT 
            p.*, 
            e.employee_code, e.first_name, e.last_name, e.designation,
            d.name AS department_name,
            u.email
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        LEFT JOIN departments d ON e.department_id = d.id
        JOIN users u ON e.user_id = u.id
        WHERE p.id = %s
    """
    record = query_db(query, (payroll_id,), one=True)
    if not record:
        flash("Salary slip record not found.", "warning")
        return redirect(url_for('admin.payroll'))

    pdf_buffer = generate_payslip_pdf(record)
    month_name = calendar.month_name[record['month']]
    filename = f"Payslip_{record['employee_code']}_{month_name}_{record['year']}.pdf"

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@admin_bp.route('/payroll/delete/<int:payroll_id>', methods=['POST'])
@admin_required
def delete_payroll(payroll_id):
    """Deletes a payroll record."""
    try:
        query_db("DELETE FROM payroll WHERE id = %s", (payroll_id,), commit=True)
        flash("Payroll record deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting payroll record: {str(e)}", "danger")

    return redirect(url_for('admin.payroll'))


# =====================================================================
# 7. TASK MANAGEMENT (ADMIN)
# =====================================================================

@admin_bp.route('/tasks')
@admin_required
def tasks():
    """
    Displays the Task Management dashboard for Admin.
    Lists all tasks with filters for Status, Priority, Department, and Search.
    Includes Task creation, status overview cards, and actions.
    """
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    department_id = request.args.get('department', '').strip()
    search = request.args.get('search', '').strip()

    departments_list = query_db("SELECT id, name FROM departments ORDER BY name ASC")
    employees_list = query_db(
        """
        SELECT e.id, e.employee_code, e.first_name, e.last_name, d.name AS department_name
        FROM employees e
        JOIN users u ON e.user_id = u.id
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE u.role = 'employee' AND u.is_active = 1
        ORDER BY e.first_name ASC
        """
    )

    tasks_list = []
    stats = {'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0}

    try:
        where_clauses = []
        params = []

        if status_filter in ['Pending', 'In Progress', 'Completed']:
            where_clauses.append("t.status = %s")
            params.append(status_filter)

        if priority_filter in ['Low', 'Medium', 'High', 'Urgent']:
            where_clauses.append("t.priority = %s")
            params.append(priority_filter)

        if department_id and department_id.isdigit():
            where_clauses.append("e.department_id = %s")
            params.append(int(department_id))

        if search:
            where_clauses.append("(t.title LIKE %s OR e.employee_code LIKE %s OR e.first_name LIKE %s OR e.last_name LIKE %s)")
            sp = f"%{search}%"
            params.extend([sp, sp, sp, sp])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
            SELECT 
                t.*,
                e.employee_code, e.first_name, e.last_name, e.designation,
                d.name AS department_name,
                u_admin.username AS assigned_by_name
            FROM tasks t
            JOIN employees e ON t.employee_id = e.id
            LEFT JOIN departments d ON e.department_id = d.id
            LEFT JOIN users u_admin ON t.assigned_by = u_admin.id
            {where_sql}
            ORDER BY t.created_at DESC
        """
        tasks_list = query_db(query, tuple(params))

        # Overall counts for stat cards
        counts = query_db(
            """
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed
            FROM tasks
            """,
            one=True
        )
        if counts:
            stats['total'] = counts['total'] or 0
            stats['pending'] = counts['pending'] or 0
            stats['in_progress'] = counts['in_progress'] or 0
            stats['completed'] = counts['completed'] or 0

    except Exception as e:
        flash(f"Error loading tasks: {str(e)}", "danger")

    return render_template(
        'admin/tasks.html',
        tasks=tasks_list,
        employees=employees_list,
        departments=departments_list,
        stats=stats,
        selected_status=status_filter,
        selected_priority=priority_filter,
        selected_dept=department_id,
        search=search,
        today=date.today()
    )


@admin_bp.route('/tasks/create', methods=['POST'])
@admin_required
def create_task():
    """Creates a new task assigned to an employee."""
    employee_id = request.form.get('employee_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'Medium').strip()
    due_date = request.form.get('due_date', '').strip() or None
    assigned_by = session.get('user_id')

    if not employee_id or not title:
        flash("Employee and Task Title are required.", "danger")
        return redirect(url_for('admin.tasks'))

    try:
        query_db(
            """
            INSERT INTO tasks (employee_id, title, description, priority, status, due_date, assigned_by)
            VALUES (%s, %s, %s, %s, 'Pending', %s, %s)
            """,
            (employee_id, title, description, priority, due_date, assigned_by),
            commit=True
        )
        flash(f"Task '{title}' assigned successfully!", "success")
    except Exception as e:
        flash(f"Failed to create task: {str(e)}", "danger")

    return redirect(url_for('admin.tasks'))


@admin_bp.route('/tasks/edit/<int:task_id>', methods=['POST'])
@admin_required
def edit_task(task_id):
    """Updates an existing task's details, status, priority, and deadline."""
    employee_id = request.form.get('employee_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'Medium').strip()
    status = request.form.get('status', 'Pending').strip()
    due_date = request.form.get('due_date', '').strip() or None

    if not employee_id or not title:
        flash("Employee and Task Title are required.", "danger")
        return redirect(url_for('admin.tasks'))

    try:
        query_db(
            """
            UPDATE tasks
            SET employee_id = %s, title = %s, description = %s,
                priority = %s, status = %s, due_date = %s
            WHERE id = %s
            """,
            (employee_id, title, description, priority, status, due_date, task_id),
            commit=True
        )
        flash("Task updated successfully!", "success")
    except Exception as e:
        flash(f"Failed to update task: {str(e)}", "danger")

    return redirect(url_for('admin.tasks'))


@admin_bp.route('/tasks/delete/<int:task_id>', methods=['POST'])
@admin_required
def delete_task(task_id):
    """Deletes a task record."""
    try:
        query_db("DELETE FROM tasks WHERE id = %s", (task_id,), commit=True)
        flash("Task deleted successfully.", "success")
    except Exception as e:
        flash(f"Failed to delete task: {str(e)}", "danger")

    return redirect(url_for('admin.tasks'))


# =====================================================================
# 8. PERFORMANCE TRACKING (ADMIN)
# =====================================================================

@admin_bp.route('/performance')
@admin_required
def performance():
    """
    Displays the Performance Tracking module for Admin.
    Includes overall rating metrics, Chart.js rating breakdown,
    list of performance reviews, and review management modal.
    """
    employee_filter = request.args.get('employee', '').strip()
    rating_filter = request.args.get('rating', '').strip()
    search = request.args.get('search', '').strip()

    employees_list = query_db(
        """
        SELECT e.id, e.employee_code, e.first_name, e.last_name, d.name AS department_name
        FROM employees e
        JOIN users u ON e.user_id = u.id
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE u.role = 'employee' AND u.is_active = 1
        ORDER BY e.first_name ASC
        """
    )

    reviews_list = []
    stats = {
        'total_reviews': 0,
        'avg_rating': 0.0,
        'five_stars': 0,
        'four_stars': 0,
        'three_stars': 0,
        'two_stars': 0,
        'one_star': 0
    }

    try:
        where_clauses = []
        params = []

        if employee_filter and employee_filter.isdigit():
            where_clauses.append("pr.employee_id = %s")
            params.append(int(employee_filter))

        if rating_filter and rating_filter.isdigit() and 1 <= int(rating_filter) <= 5:
            where_clauses.append("pr.rating = %s")
            params.append(int(rating_filter))

        if search:
            where_clauses.append("(e.employee_code LIKE %s OR e.first_name LIKE %s OR e.last_name LIKE %s OR pr.review_period LIKE %s)")
            sp = f"%{search}%"
            params.extend([sp, sp, sp, sp])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
            SELECT 
                pr.*,
                e.employee_code, e.first_name, e.last_name, e.designation,
                d.name AS department_name,
                u_rev.username AS reviewer_name
            FROM performance_reviews pr
            JOIN employees e ON pr.employee_id = e.id
            LEFT JOIN departments d ON e.department_id = d.id
            JOIN users u_rev ON pr.reviewer_id = u_rev.id
            {where_sql}
            ORDER BY pr.created_at DESC
        """
        reviews_list = query_db(query, tuple(params))

        # Global stats across all reviews
        all_reviews = query_db("SELECT rating FROM performance_reviews")
        if all_reviews:
            stats['total_reviews'] = len(all_reviews)
            total_sum = sum(r['rating'] for r in all_reviews)
            stats['avg_rating'] = round(total_sum / len(all_reviews), 1)

            for r in all_reviews:
                rt = r['rating']
                if rt == 5:
                    stats['five_stars'] += 1
                elif rt == 4:
                    stats['four_stars'] += 1
                elif rt == 3:
                    stats['three_stars'] += 1
                elif rt == 2:
                    stats['two_stars'] += 1
                elif rt == 1:
                    stats['one_star'] += 1

    except Exception as e:
        flash(f"Error loading performance reviews: {str(e)}", "danger")

    return render_template(
        'admin/performance.html',
        reviews=reviews_list,
        employees=employees_list,
        stats=stats,
        selected_employee=employee_filter,
        selected_rating=rating_filter,
        search=search
    )


@admin_bp.route('/performance/add', methods=['POST'])
@admin_required
def add_performance_review():
    """Adds a new performance review with rating, feedback, and achievements."""
    employee_id = request.form.get('employee_id')
    review_period = request.form.get('review_period', '').strip()
    rating_str = request.form.get('rating', '5').strip()
    comments = request.form.get('comments', '').strip()
    achievements = request.form.get('achievements', '').strip()
    reviewer_id = session.get('user_id')

    if not employee_id or not review_period or not comments:
        flash("Employee, Review Period, and Feedback comments are required.", "danger")
        return redirect(url_for('admin.performance'))

    try:
        rating = int(rating_str)
        if not 1 <= rating <= 5:
            flash("Rating must be between 1 and 5.", "danger")
            return redirect(url_for('admin.performance'))

        query_db(
            """
            INSERT INTO performance_reviews
                (employee_id, reviewer_id, review_period, rating, comments, achievements)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (employee_id, reviewer_id, review_period, rating, comments, achievements),
            commit=True
        )
        flash("Performance review recorded successfully!", "success")
    except ValueError:
        flash("Invalid rating format.", "danger")
    except Exception as e:
        flash(f"Failed to record review: {str(e)}", "danger")

    return redirect(url_for('admin.performance'))


@admin_bp.route('/performance/edit/<int:review_id>', methods=['POST'])
@admin_required
def edit_performance_review(review_id):
    """Updates an existing performance review."""
    review_period = request.form.get('review_period', '').strip()
    rating_str = request.form.get('rating', '5').strip()
    comments = request.form.get('comments', '').strip()
    achievements = request.form.get('achievements', '').strip()

    if not review_period or not comments:
        flash("Review Period and Feedback comments are required.", "danger")
        return redirect(url_for('admin.performance'))

    try:
        rating = int(rating_str)
        if not 1 <= rating <= 5:
            flash("Rating must be between 1 and 5.", "danger")
            return redirect(url_for('admin.performance'))

        query_db(
            """
            UPDATE performance_reviews
            SET review_period = %s, rating = %s, comments = %s, achievements = %s
            WHERE id = %s
            """,
            (review_period, rating, comments, achievements, review_id),
            commit=True
        )
        flash("Performance review updated successfully!", "success")
    except ValueError:
        flash("Invalid rating value.", "danger")
    except Exception as e:
        flash(f"Failed to update review: {str(e)}", "danger")

    return redirect(url_for('admin.performance'))


@admin_bp.route('/performance/delete/<int:review_id>', methods=['POST'])
@admin_required
def delete_performance_review(review_id):
    """Deletes a performance review record."""
    try:
        query_db("DELETE FROM performance_reviews WHERE id = %s", (review_id,), commit=True)
        flash("Performance review deleted successfully.", "success")
    except Exception as e:
        flash(f"Failed to delete review: {str(e)}", "danger")

    return redirect(url_for('admin.performance'))


@admin_bp.route('/performance/employee/<int:emp_id>')
@admin_required
def employee_performance_history(emp_id):
    """Displays the complete performance review history for an individual employee."""
    try:
        emp = query_db(
            """
            SELECT e.*, d.name AS department_name, u.email
            FROM employees e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN departments d ON e.department_id = d.id
            WHERE e.id = %s
            """,
            (emp_id,),
            one=True
        )
        if not emp:
            flash("Employee not found.", "warning")
            return redirect(url_for('admin.performance'))

        reviews = query_db(
            """
            SELECT pr.*, u.username AS reviewer_name
            FROM performance_reviews pr
            JOIN users u ON pr.reviewer_id = u.id
            WHERE pr.employee_id = %s
            ORDER BY pr.created_at DESC
            """,
            (emp_id,)
        )

        avg_rating = 0.0
        if reviews:
            avg_rating = round(sum(r['rating'] for r in reviews) / len(reviews), 1)

        return render_template(
            'admin/employee_performance.html',
            employee=emp,
            reviews=reviews,
            avg_rating=avg_rating
        )
    except Exception as e:
        flash(f"Error loading employee history: {str(e)}", "danger")
        return redirect(url_for('admin.performance'))

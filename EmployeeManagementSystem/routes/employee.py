"""
Employee Routes Module - Employee Management System
Handles Employee Portal Dashboard, Attendance (Clock In/Out, History, Percentage),
and Leave Management (Apply, View Status & History).
"""

from datetime import datetime, date, timedelta
import calendar
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, abort
from routes.auth import employee_required
from database import query_db
from utils.pdf_generator import generate_payslip_pdf

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')


# =====================================================================
# 1. EMPLOYEE DASHBOARD
# =====================================================================

@employee_bp.route('/dashboard')
@employee_required
def dashboard():
    """
    Employee Portal Dashboard showing personal overview, today's punch status,
    attendance percentage, and quick actions.
    """
    employee_id = session.get('employee_id')
    emp_data = None
    today_attendance = None
    pending_tasks = 0
    pending_leaves = 0
    attendance_pct = 0.0

    try:
        if employee_id:
            # 1. Fetch employee profile details
            emp_data = query_db(
                """
                SELECT e.*, d.name AS department_name, u.email, u.username
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.id
                JOIN users u ON e.user_id = u.id
                WHERE e.id = %s
                """,
                (employee_id,),
                one=True
            )

            # 2. Check today's attendance record
            today_attendance = query_db(
                "SELECT * FROM attendance WHERE employee_id = %s AND date = CURDATE()",
                (employee_id,),
                one=True
            )

            # 3. Count pending tasks
            tasks_res = query_db(
                "SELECT COUNT(*) AS total FROM tasks WHERE employee_id = %s AND status != 'Completed'",
                (employee_id,),
                one=True
            )
            if tasks_res:
                pending_tasks = tasks_res['total']

            # 4. Count pending leave requests
            leaves_res = query_db(
                "SELECT COUNT(*) AS total FROM leave_requests WHERE employee_id = %s AND status = 'Pending'",
                (employee_id,),
                one=True
            )
            if leaves_res:
                pending_leaves = leaves_res['total']

            # 5. Calculate current month attendance percentage
            now = date.today()
            current_month = now.month
            current_year = now.year

            total_days_res = query_db(
                """
                SELECT COUNT(*) AS total FROM attendance 
                WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s
                """,
                (employee_id, current_month, current_year),
                one=True
            )
            present_days_res = query_db(
                """
                SELECT COUNT(*) AS total FROM attendance 
                WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s AND status = 'Present'
                """,
                (employee_id, current_month, current_year),
                one=True
            )
            half_days_res = query_db(
                """
                SELECT COUNT(*) AS total FROM attendance 
                WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s AND status = 'Half Day'
                """,
                (employee_id, current_month, current_year),
                one=True
            )

            total_logged = total_days_res['total'] if total_days_res else 0
            present_logged = present_days_res['total'] if present_days_res else 0
            half_logged = half_days_res['total'] if half_days_res else 0

            if total_logged > 0:
                attendance_pct = round(((present_logged + (half_logged * 0.5)) / total_logged) * 100, 1)

    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")

    return render_template(
        'employee/dashboard.html',
        employee=emp_data,
        today_attendance=today_attendance,
        pending_tasks=pending_tasks,
        pending_leaves=pending_leaves,
        attendance_pct=attendance_pct
    )


# =====================================================================
# 2. ATTENDANCE MANAGEMENT (EMPLOYEE VIEW)
# =====================================================================

@employee_bp.route('/attendance')
@employee_required
def attendance():
    """
    Displays the employee's personal attendance history, monthly logs,
    and attendance percentage with month/year selector.
    """
    employee_id = session.get('employee_id')
    
    # Selected Month and Year (defaults to current date)
    today = date.today()
    try:
        selected_month = int(request.args.get('month', today.month))
        selected_year = int(request.args.get('year', today.year))
    except ValueError:
        selected_month = today.month
        selected_year = today.year

    attendance_records = []
    stats = {
        'total_logged': 0,
        'present': 0,
        'absent': 0,
        'half_day': 0,
        'leave': 0,
        'percentage': 0.0
    }
    today_record = None

    try:
        if employee_id:
            # Check today's record
            today_record = query_db(
                "SELECT * FROM attendance WHERE employee_id = %s AND date = CURDATE()",
                (employee_id,),
                one=True
            )

            # Monthly attendance logs
            attendance_records = query_db(
                """
                SELECT * FROM attendance 
                WHERE employee_id = %s AND MONTH(date) = %s AND YEAR(date) = %s
                ORDER BY date DESC
                """,
                (employee_id, selected_month, selected_year)
            )

            # Compute monthly statistics
            stats['total_logged'] = len(attendance_records)
            for rec in attendance_records:
                st = rec['status']
                if st == 'Present':
                    stats['present'] += 1
                elif st == 'Absent':
                    stats['absent'] += 1
                elif st == 'Half Day':
                    stats['half_day'] += 1
                elif st in ['Leave', 'On Leave']:
                    stats['leave'] += 1

            if stats['total_logged'] > 0:
                stats['percentage'] = round(
                    ((stats['present'] + (stats['half_day'] * 0.5)) / stats['total_logged']) * 100, 1
                )

    except Exception as e:
        flash(f"Error loading attendance history: {str(e)}", "danger")

    month_name = calendar.month_name[selected_month]

    return render_template(
        'employee/attendance.html',
        attendance_records=attendance_records,
        stats=stats,
        today_record=today_record,
        selected_month=selected_month,
        selected_year=selected_year,
        month_name=month_name
    )


@employee_bp.route('/attendance/clock-in', methods=['POST'])
@employee_required
def clock_in():
    """
    Allows employee to punch in for today.
    Records clock_in time and sets status to 'Present'.
    """
    employee_id = session.get('employee_id')
    today_date = date.today()
    now_time = datetime.now().strftime('%H:%M:%S')

    try:
        # Check if record already exists for today
        existing = query_db(
            "SELECT id, clock_in FROM attendance WHERE employee_id = %s AND date = %s",
            (employee_id, today_date),
            one=True
        )

        if existing and existing['clock_in']:
            flash(f"You have already clocked in today at {existing['clock_in']}.", "info")
        elif existing:
            # Update existing record
            query_db(
                "UPDATE attendance SET clock_in = %s, status = 'Present' WHERE id = %s",
                (now_time, existing['id']),
                commit=True
            )
            flash(f"Clocked in successfully at {now_time}!", "success")
        else:
            # Insert new attendance record
            query_db(
                """
                INSERT INTO attendance (employee_id, date, clock_in, status)
                VALUES (%s, %s, %s, 'Present')
                """,
                (employee_id, today_date, now_time),
                commit=True
            )
            flash(f"Clocked in successfully at {now_time}!", "success")

    except Exception as e:
        flash(f"Failed to clock in: {str(e)}", "danger")

    return redirect(request.referrer or url_for('employee.dashboard'))


@employee_bp.route('/attendance/clock-out', methods=['POST'])
@employee_required
def clock_out():
    """
    Allows employee to punch out for today.
    Records clock_out time.
    """
    employee_id = session.get('employee_id')
    today_date = date.today()
    now_time = datetime.now().strftime('%H:%M:%S')

    try:
        existing = query_db(
            "SELECT id, clock_out FROM attendance WHERE employee_id = %s AND date = %s",
            (employee_id, today_date),
            one=True
        )

        if not existing:
            # If not yet clocked in, create record with clock_out
            query_db(
                """
                INSERT INTO attendance (employee_id, date, clock_out, status)
                VALUES (%s, %s, %s, 'Present')
                """,
                (employee_id, today_date, now_time),
                commit=True
            )
            flash(f"Clocked out successfully at {now_time}!", "success")
        else:
            query_db(
                "UPDATE attendance SET clock_out = %s WHERE id = %s",
                (now_time, existing['id']),
                commit=True
            )
            flash(f"Clocked out successfully at {now_time}!", "success")

    except Exception as e:
        flash(f"Failed to clock out: {str(e)}", "danger")

    return redirect(request.referrer or url_for('employee.dashboard'))


# =====================================================================
# 3. LEAVE MANAGEMENT (EMPLOYEE VIEW)
# =====================================================================

@employee_bp.route('/leaves')
@employee_required
def leaves():
    """
    Displays the employee's personal leave requests history,
    status badges (Pending, Approved, Rejected), and leave application modal.
    """
    employee_id = session.get('employee_id')
    leaves_list = []
    stats = {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0}

    try:
        if employee_id:
            leaves_list = query_db(
                """
                SELECT * FROM leave_requests 
                WHERE employee_id = %s 
                ORDER BY applied_at DESC
                """,
                (employee_id,)
            )

            stats['total'] = len(leaves_list)
            for lv in leaves_list:
                st = lv['status'].lower()
                if st == 'pending':
                    stats['pending'] += 1
                elif st == 'approved':
                    stats['approved'] += 1
                elif st == 'rejected':
                    stats['rejected'] += 1

    except Exception as e:
        flash(f"Error loading leave records: {str(e)}", "danger")

    return render_template('employee/leaves.html', leaves=leaves_list, stats=stats)


@employee_bp.route('/leaves/apply', methods=['POST'])
@employee_required
def apply_leave():
    """
    Submits a new leave request.
    Validates date range and reason, prevents duplicate overlapping leaves.
    """
    employee_id = session.get('employee_id')
    leave_type = request.form.get('leave_type', '').strip()
    start_date_str = request.form.get('start_date', '').strip()
    end_date_str = request.form.get('end_date', '').strip()
    reason = request.form.get('reason', '').strip()

    # Form input validations
    if not leave_type or not start_date_str or not end_date_str or not reason:
        flash("All fields (Leave Type, Start Date, End Date, Reason) are required.", "danger")
        return redirect(url_for('employee.leaves'))

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        if end_date < start_date:
            flash("End Date cannot be earlier than Start Date.", "danger")
            return redirect(url_for('employee.leaves'))

        # Calculate number of leave days inclusive
        total_days = (end_date - start_date).days + 1

        # Check for overlapping pending or approved leave requests
        overlap = query_db(
            """
            SELECT id FROM leave_requests
            WHERE employee_id = %s 
              AND status != 'Rejected'
              AND (
                  (start_date BETWEEN %s AND %s) OR
                  (end_date BETWEEN %s AND %s) OR
                  (%s BETWEEN start_date AND end_date)
              )
            LIMIT 1
            """,
            (employee_id, start_date, end_date, start_date, end_date, start_date),
            one=True
        )

        if overlap:
            flash("You already have an active/pending leave application covering these dates.", "warning")
            return redirect(url_for('employee.leaves'))

        # Insert leave application
        query_db(
            """
            INSERT INTO leave_requests (
                employee_id, leave_type, start_date, end_date, total_days, reason, status
            ) VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
            """,
            (employee_id, leave_type, start_date, end_date, total_days, reason),
            commit=True
        )

        flash(f"Leave application for {total_days} day(s) submitted successfully! Awaiting HR approval.", "success")

    except ValueError:
        flash("Invalid date format entered. Please use YYYY-MM-DD.", "danger")
    except Exception as e:
        flash(f"Failed to submit leave application: {str(e)}", "danger")

    return redirect(url_for('employee.leaves'))


# =====================================================================
# 4. EMPLOYEE PROFILE VIEW
# =====================================================================

@employee_bp.route('/profile')
@employee_required
def profile():
    """
    Displays the employee's personal profile.
    """
    employee_id = session.get('employee_id')
    emp = None
    try:
        if employee_id:
            emp = query_db(
                """
                SELECT e.*, d.name AS department_name, u.email, u.username, u.is_active
                FROM employees e
                JOIN users u ON e.user_id = u.id
                LEFT JOIN departments d ON e.department_id = d.id
                WHERE e.id = %s
                """,
                (employee_id,),
                one=True
            )
    except Exception as e:
        flash(f"Error loading profile: {str(e)}", "danger")

    return render_template('employee/profile.html', employee=emp)


# =====================================================================
# 5. PERSONAL SALARY & PAYROLL SLIPS (EMPLOYEE)
# =====================================================================

@employee_bp.route('/payroll')
@employee_required
def payroll():
    """
    Displays the employee's personal salary details, compensation structure,
    and monthly payslip history.
    """
    employee_id = session.get('employee_id')
    payslips = []
    emp_profile = None
    stats = {'total_slips': 0, 'basic_salary': 0.0, 'latest_net': 0.0}

    try:
        if employee_id:
            emp_profile = query_db(
                """
                SELECT e.*, d.name AS department_name
                FROM employees e
                LEFT JOIN departments d ON e.department_id = d.id
                WHERE e.id = %s
                """,
                (employee_id,),
                one=True
            )
            if emp_profile:
                stats['basic_salary'] = float(emp_profile['basic_salary'] or 0)

            # Fetch all past payroll records for this employee
            payslips = query_db(
                """
                SELECT * FROM payroll
                WHERE employee_id = %s
                ORDER BY year DESC, month DESC
                """,
                (employee_id,)
            )

            stats['total_slips'] = len(payslips)
            if payslips:
                stats['latest_net'] = float(payslips[0]['net_salary'] or 0)

    except Exception as e:
        flash(f"Error loading salary history: {str(e)}", "danger")

    return render_template(
        'employee/payroll.html',
        payslips=payslips,
        employee=emp_profile,
        stats=stats
    )


@employee_bp.route('/payroll/slip/<int:payroll_id>')
@employee_required
def view_payslip(payroll_id):
    """
    Displays personal printable salary slip.
    Strictly verifies employee ownership to prevent unauthorized access.
    """
    employee_id = session.get('employee_id')

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
        return redirect(url_for('employee.payroll'))

    # Security Check: Ensure employee only views their own payslip
    if record['employee_id'] != employee_id:
        abort(403)

    month_name = calendar.month_name[record['month']]
    return render_template('employee/payslip.html', slip=record, month_name=month_name)


@employee_bp.route('/payroll/pdf/<int:payroll_id>')
@employee_required
def download_payslip_pdf(payroll_id):
    """
    Downloads personal salary slip as a PDF.
    Strictly verifies employee ownership.
    """
    employee_id = session.get('employee_id')

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
        return redirect(url_for('employee.payroll'))

    # Security Check
    if record['employee_id'] != employee_id:
        abort(403)

    pdf_buffer = generate_payslip_pdf(record)
    month_name = calendar.month_name[record['month']]
    filename = f"Payslip_{record['employee_code']}_{month_name}_{record['year']}.pdf"

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )



# =====================================================================
# 6. ASSIGNED TASK MANAGEMENT (EMPLOYEE VIEW)
# =====================================================================

@employee_bp.route('/tasks')
@employee_required
def tasks():
    """
    Displays the tasks assigned to the currently logged-in employee.
    Includes task progress tracking, deadlines, priority badges, and quick status update.
    """
    employee_id = session.get('employee_id')
    status_filter = request.args.get('status', '').strip()

    tasks_list = []
    stats = {'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0}

    try:
        where_clauses = ["t.employee_id = %s"]
        params = [employee_id]

        if status_filter in ['Pending', 'In Progress', 'Completed']:
            where_clauses.append("t.status = %s")
            params.append(status_filter)

        where_sql = " WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT 
                t.*,
                u.username AS assigned_by_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_by = u.id
            {where_sql}
            ORDER BY 
                CASE 
                    WHEN t.status = 'In Progress' THEN 1
                    WHEN t.status = 'Pending' THEN 2
                    WHEN t.status = 'Completed' THEN 3
                    ELSE 4
                END,
                t.due_date ASC,
                t.created_at DESC
        """
        tasks_list = query_db(query, tuple(params))

        # Stats across all tasks for this employee
        counts = query_db(
            """
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed
            FROM tasks
            WHERE employee_id = %s
            """,
            (employee_id,),
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
        'employee/tasks.html',
        tasks=tasks_list,
        stats=stats,
        selected_status=status_filter,
        today=date.today()
    )


@employee_bp.route('/tasks/update/<int:task_id>', methods=['POST'])
@employee_required
def update_task_status(task_id):
    """
    Updates the status of an assigned task.
    Strictly checks that the task belongs to the logged-in employee.
    """
    employee_id = session.get('employee_id')
    new_status = request.form.get('status', '').strip()

    if new_status not in ['Pending', 'In Progress', 'Completed']:
        flash("Invalid status selection.", "danger")
        return redirect(url_for('employee.tasks'))

    try:
        # Verify ownership
        task = query_db(
            "SELECT id, title FROM tasks WHERE id = %s AND employee_id = %s",
            (task_id, employee_id),
            one=True
        )
        if not task:
            abort(403)

        query_db(
            "UPDATE tasks SET status = %s WHERE id = %s",
            (new_status, task_id),
            commit=True
        )
        flash(f"Task '{task['title']}' updated to '{new_status}'.", "success")
    except Exception as e:
        flash(f"Failed to update task status: {str(e)}", "danger")

    return redirect(url_for('employee.tasks'))


# =====================================================================
# 7. PERFORMANCE TRACKING (EMPLOYEE VIEW)
# =====================================================================

@employee_bp.route('/performance')
@employee_required
def performance():
    """
    Displays the employee's personal performance reviews, feedback, and achievements.
    Strictly limited to the logged-in employee's own records.
    """
    employee_id = session.get('employee_id')
    reviews_list = []
    stats = {
        'total_reviews': 0,
        'avg_rating': 0.0,
        'latest_rating': 0,
        'five_stars': 0,
        'four_stars': 0,
        'three_stars': 0,
        'two_stars': 0,
        'one_star': 0
    }

    try:
        query = """
            SELECT 
                pr.*,
                u.username AS reviewer_name
            FROM performance_reviews pr
            JOIN users u ON pr.reviewer_id = u.id
            WHERE pr.employee_id = %s
            ORDER BY pr.created_at DESC
        """
        reviews_list = query_db(query, (employee_id,))

        if reviews_list:
            stats['total_reviews'] = len(reviews_list)
            stats['latest_rating'] = reviews_list[0]['rating']
            total_sum = sum(r['rating'] for r in reviews_list)
            stats['avg_rating'] = round(total_sum / len(reviews_list), 1)

            for r in reviews_list:
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
        'employee/performance.html',
        reviews=reviews_list,
        stats=stats
    )

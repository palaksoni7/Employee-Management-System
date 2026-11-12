import os
import click
from flask import Flask, redirect, url_for, session, render_template, jsonify
from config import Config
from database import init_db, test_connection
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.employee import employee_bp

def create_app():
    """Application factory for the Employee Management System."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Automatically initialize tables and default seed data on startup
    try:
        init_db()
    except Exception as e:
        print(f"[Startup Database Note] Automatic DB initialization skipped or deferred: {e}")

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(employee_bp, url_prefix='/employee')

    # Root route - role-based dispatch
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('employee.dashboard'))

    # Health & Diagnostics Route
    @app.route('/health')
    def health():
        db_ok, db_msg = test_connection()
        return jsonify({
            'status': 'healthy' if db_ok else 'unhealthy',
            'app_name': Config.APP_NAME,
            'database': {
                'connected': db_ok,
                'message': db_msg,
                'host': Config.DB_HOST,
                'port': Config.DB_PORT,
                'database_name': Config.DB_NAME,
                'user': Config.DB_USER
            }
        }), 200 if db_ok else 500

    # Command-line interface to initialize DB: flask --app app init-db
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize the database from schema.sql and seed default admin."""
        success, message = init_db()
        if success:
            print("[Success]", message)
        else:
            print("[Error]", message)

    # Command-line interface to securely create an admin: flask --app app create-admin
    @app.cli.command('create-admin')
    @click.option('--username', prompt='Admin username', default='admin', help='Username for the admin')
    @click.option('--email', prompt='Admin email', default='admin@ems.com', help='Email for the admin')
    @click.option('--password', prompt='Admin password', hide_input=True, confirmation_prompt=True, help='Password for the admin')
    def create_admin_command(username, email, password):
        """Securely create a new administrator account with a hashed password."""
        from werkzeug.security import generate_password_hash
        from database import query_db
        try:
            # Check if user already exists
            existing = query_db(
                "SELECT id FROM users WHERE username = %s OR email = %s",
                (username, email),
                one=True
            )
            if existing:
                print(f"[Error] An account with username '{username}' or email '{email}' already exists.")
                return

            hashed_pw = generate_password_hash(password)
            query_db(
                """
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, 'admin', 1)
                """,
                (username, email, hashed_pw),
                commit=True
            )
            print(f"[Success] Admin account '{username}' created successfully!")
        except Exception as e:
            print(f"[Error] Failed to create admin: {e}")

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    # Try automatic database setup on startup if needed
    try:
        init_db()
    except Exception as e:
        print(f"[Startup Warning] Automatic DB init skipped: {e}")

    app.run(host='0.0.0.0', port=5000, debug=True)

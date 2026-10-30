"""Flask application factory."""

import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from sqlalchemy import event
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.config import Config
from backend.extensions import db


FRONTEND = ROOT / "frontend"


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(test_config=None):
    app = Flask(
        __name__, static_folder=str(FRONTEND), static_url_path="/static",
        instance_path=str(ROOT / "instance"),
    )
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(Config)
    if not os.getenv("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)

    from backend.routes.academics import bp as academics_bp
    from backend.routes.auth import bp as auth_bp
    from backend.routes.dashboard import bp as dashboard_bp
    from backend.routes.students import bp as students_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(academics_bp)
    app.register_blueprint(dashboard_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND, "index.html")

    @app.get("/<page>.html")
    def frontend_page(page):
        if page not in {"index", "login", "students", "departments", "courses", "attendance", "results", "reports"}:
            return jsonify({"error": "Page not found."}), 404
        return send_from_directory(FRONTEND, f"{page}.html")

    with app.app_context():
        db.create_all()
        from backend.models import User
        admin_email = app.config["ADMIN_EMAIL"]
        if not User.query.filter_by(email=admin_email).first():
            admin_password = app.config.get("ADMIN_PASSWORD")
            if not admin_password:
                db.session.remove()
                db.engine.dispose()
                raise RuntimeError("Set ADMIN_PASSWORD before the first application startup.")
            admin = User(email=admin_email, full_name="System Administrator")
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()

    return app

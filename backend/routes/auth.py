import re

from flask import Blueprint, current_app, jsonify
from itsdangerous import URLSafeTimedSerializer

from backend.models import User
from backend.routes.common import (
    commit_or_error,
    error,
    payload,
    require_auth,
    required_text,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def issue_token(user):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"]).dumps(
        user.id, salt="student-management-auth"
    )


@bp.post("/register")
def register():
    try:
        data = payload()
        full_name = required_text(data, "full_name", "Full name", 120)
        email = required_text(data, "email", "Email", 255).lower()
        password = required_text(data, "password", "Password", 256)
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
    except ValueError as exc:
        return error(str(exc))

    user = User(email=email, full_name=full_name)
    user.set_password(password)
    from backend.extensions import db

    db.session.add(user)
    failure = commit_or_error()
    if failure:
        return failure
    return jsonify({"token": issue_token(user), "user": user.to_dict()}), 201


@bp.post("/login")
def login():
    try:
        data = payload()
        email = required_text(data, "email", "Email", 255).lower()
        password = required_text(data, "password", "Password", 256)
    except ValueError as exc:
        return error(str(exc))
    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return error("Email or password is incorrect.", 401)
    return jsonify({"token": issue_token(user), "user": user.to_dict()})


@bp.get("/me")
@require_auth
def me():
    from flask import request
    return jsonify({"user": request.current_user.to_dict()})


@bp.post("/logout")
@require_auth
def logout():
    return jsonify({"message": "Signed out successfully."})

from datetime import date
from functools import wraps

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import User


def error(message, status=400):
    return jsonify({"error": message}), status


def require_auth(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        token = request.headers.get("Authorization", "")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        else:
            return error("Authentication required.", 401)
        try:
            user_id = URLSafeTimedSerializer(current_app.config["SECRET_KEY"]).loads(
                token, salt="student-management-auth",
                max_age=current_app.config["TOKEN_MAX_AGE"],
            )
        except SignatureExpired:
            return error("Session expired. Please sign in again.", 401)
        except BadSignature:
            return error("Invalid authentication token.", 401)
        user = db.session.get(User, user_id)
        if user is None:
            return error("User account no longer exists.", 401)
        request.current_user = user
        return handler(*args, **kwargs)
    return wrapped


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return data


def required_text(data, key, label, maximum=255):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    return value


def optional_text(data, key, label, maximum=1000):
    value = data.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    return value


def integer_value(data, key, label, minimum=1, maximum=12, default=None):
    value = data.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a whole number.")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{label} must be a whole number.")
    if result < minimum or result > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return result


def parse_date(value, label, required=False):
    if not value:
        if required:
            raise ValueError(f"{label} is required.")
        return None
    try:
        result = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must use YYYY-MM-DD format.")
    if result > date.today():
        raise ValueError(f"{label} cannot be in the future.")
    return result


def commit_or_error():
    try:
        db.session.commit()
        return None
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning("Rejected a database record with conflicting unique or foreign-key values.")
        return error("The record could not be saved. Check for duplicate values or invalid references.", 409)

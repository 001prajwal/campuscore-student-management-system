import os


def database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///student_management.db")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "local-development-key-change-before-deploy")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    TOKEN_MAX_AGE = 60 * 60 * 12
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

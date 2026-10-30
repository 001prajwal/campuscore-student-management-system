import re

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models import Course, Department, Student
from backend.routes.common import (
    commit_or_error, error, integer_value, optional_text, parse_date, payload,
    require_auth, required_text,
)

bp = Blueprint("students", __name__, url_prefix="/api/students")
GENDERS = {"Female", "Male", "Non-binary", "Prefer not to say"}
STATUSES = {"Active", "Inactive", "Graduated", "Suspended"}


def student_values(data, student=None):
    def get(key, default=None):
        return data[key] if key in data else default

    values = {}
    if student is None or "student_id" in data:
        values["student_id"] = required_text({"v": get("student_id", "")}, "v", "Student ID", 32).upper()
    if student is None or "full_name" in data:
        values["full_name"] = required_text({"v": get("full_name", "")}, "v", "Full name", 120)
    if student is None or "email" in data:
        email = required_text({"v": get("email", "")}, "v", "Email", 255).lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address.")
        values["email"] = email
    if student is None or "phone" in data:
        phone = optional_text({"v": get("phone", "")}, "v", "Phone number", 32)
        if phone and not re.fullmatch(r"[+()\d.\-\s]{7,32}", phone):
            raise ValueError("Enter a valid phone number.")
        values["phone"] = phone
    if student is None or "gender" in data:
        gender = get("gender", "Prefer not to say")
        if gender not in GENDERS:
            raise ValueError("Choose a valid gender option.")
        values["gender"] = gender
    if student is None or "date_of_birth" in data:
        values["date_of_birth"] = parse_date(get("date_of_birth"), "Date of birth")
    if student is None or "address" in data:
        values["address"] = optional_text({"v": get("address", "")}, "v", "Address", 1000)
    if student is None or "department_id" in data:
        values["department_id"] = integer_value({"v": get("department_id")}, "v", "Department")
        if db.session.get(Department, values["department_id"]) is None:
            raise ValueError("Selected department does not exist.")
    if student is None or "course_id" in data:
        values["course_id"] = integer_value({"v": get("course_id")}, "v", "Course")
        course = db.session.get(Course, values["course_id"])
        if course is None:
            raise ValueError("Selected course does not exist.")
        department_id = values.get("department_id", student.department_id if student else None)
        if department_id != course.department_id:
            raise ValueError("The selected course must belong to the selected department.")
    if student is None or "year_of_study" in data:
        values["year_of_study"] = integer_value({"v": get("year_of_study", 1)}, "v", "Year of study", 1, 12)
    if student is None or "admission_date" in data:
        values["admission_date"] = parse_date(get("admission_date"), "Admission date", required=True)
    if student is None or "profile_photo" in data:
        photo = optional_text({"v": get("profile_photo", "")}, "v", "Profile photo URL", 500)
        if photo and not photo.startswith(("https://", "http://")):
            raise ValueError("Profile photo must be an http or https URL.")
        values["profile_photo"] = photo
    if student is None or "status" in data:
        status = get("status", "Active")
        if status not in STATUSES:
            raise ValueError("Choose a valid student status.")
        values["status"] = status
    if student and ("department_id" in values or "course_id" in values):
        department_id = values.get("department_id", student.department_id)
        course_id = values.get("course_id", student.course_id)
        course = db.session.get(Course, course_id)
        if course is None or course.department_id != department_id:
            raise ValueError("The selected course must belong to the selected department.")
    return values


@bp.get("")
@require_auth
def list_students():
    query = Student.query
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(db.or_(Student.full_name.ilike(pattern), Student.student_id.ilike(pattern), Student.email.ilike(pattern)))
    for arg, column in (("department_id", Student.department_id), ("course_id", Student.course_id)):
        if request.args.get(arg):
            try:
                query = query.filter(column == int(request.args[arg]))
            except ValueError:
                return error(f"{arg} must be a whole number.")
    if request.args.get("status"):
        if request.args["status"] not in STATUSES:
            return error("Invalid status filter.")
        query = query.filter_by(status=request.args["status"])
    students = query.order_by(Student.full_name).all()
    return jsonify({"students": [row.to_dict() for row in students], "total": len(students)})


@bp.post("")
@require_auth
def create_student():
    try:
        student = Student(**student_values(payload()))
    except ValueError as exc:
        return error(str(exc))
    db.session.add(student)
    result = commit_or_error()
    return result or (jsonify({"student": student.to_dict()}), 201)


@bp.get("/<int:student_id>")
@require_auth
def get_student(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        return error("Student not found.", 404)
    return jsonify({"student": student.to_dict(include_records=True)})


@bp.put("/<int:student_id>")
@require_auth
def update_student(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        return error("Student not found.", 404)
    try:
        for key, value in student_values(payload(), student).items():
            setattr(student, key, value)
    except ValueError as exc:
        return error(str(exc))
    result = commit_or_error()
    return result or jsonify({"student": student.to_dict()})


@bp.delete("/<int:student_id>")
@require_auth
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        return error("Student not found.", 404)
    db.session.delete(student)
    result = commit_or_error()
    return result or jsonify({"message": "Student and associated records deleted."})

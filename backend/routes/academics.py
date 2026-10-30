from math import isfinite

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models import Attendance, Course, Department, Result, Student, Subject
from backend.routes.common import (
    commit_or_error, error, integer_value, optional_text, parse_date, payload,
    require_auth, required_text,
)

bp = Blueprint("academics", __name__, url_prefix="/api")
ATTENDANCE_STATUSES = {"Present", "Absent", "Late", "Excused"}


@bp.route("/departments", methods=["GET", "POST"])
@require_auth
def departments():
    if request.method == "GET":
        rows = Department.query.order_by(Department.name).all()
        return jsonify({"departments": [row.to_dict() for row in rows]})
    try:
        data = payload()
        department = Department(
            name=required_text(data, "name", "Department name", 120),
            code=required_text(data, "code", "Department code", 20).upper(),
            description=optional_text(data, "description", "Description"),
        )
    except ValueError as exc:
        return error(str(exc))
    db.session.add(department)
    result = commit_or_error()
    return result or (jsonify({"department": department.to_dict()}), 201)


@bp.route("/departments/<int:department_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def department_detail(department_id):
    department = db.session.get(Department, department_id)
    if department is None:
        return error("Department not found.", 404)
    if request.method == "GET":
        return jsonify({"department": department.to_dict()})
    if request.method == "DELETE":
        if department.students or department.courses:
            return error("Move or remove this department's students and courses before deleting it.", 409)
        db.session.delete(department)
        result = commit_or_error()
        return result or jsonify({"message": "Department deleted."})
    try:
        data = payload()
        if "name" in data:
            department.name = required_text(data, "name", "Department name", 120)
        if "code" in data:
            department.code = required_text(data, "code", "Department code", 20).upper()
        if "description" in data:
            department.description = optional_text(data, "description", "Description")
    except ValueError as exc:
        return error(str(exc))
    result = commit_or_error()
    return result or jsonify({"department": department.to_dict()})


@bp.route("/courses", methods=["GET", "POST"])
@require_auth
def courses():
    if request.method == "GET":
        query = Course.query
        if request.args.get("department_id"):
            try:
                query = query.filter_by(department_id=int(request.args["department_id"]))
            except ValueError:
                return error("department_id must be a whole number.")
        return jsonify({"courses": [row.to_dict() for row in query.order_by(Course.name).all()]})
    try:
        data = payload()
        department_id = integer_value(data, "department_id", "Department")
        if db.session.get(Department, department_id) is None:
            return error("Selected department does not exist.")
        course = Course(
            name=required_text(data, "name", "Course name", 120),
            code=required_text(data, "code", "Course code", 20).upper(),
            department_id=department_id,
            duration_years=integer_value(data, "duration_years", "Duration", 1, 12, 4),
            description=optional_text(data, "description", "Description"),
        )
    except ValueError as exc:
        return error(str(exc))
    db.session.add(course)
    result = commit_or_error()
    return result or (jsonify({"course": course.to_dict()}), 201)


@bp.route("/courses/<int:course_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def course_detail(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        return error("Course not found.", 404)
    if request.method == "GET":
        return jsonify({"course": course.to_dict()})
    if request.method == "DELETE":
        if course.students or Subject.query.filter_by(course_id=course.id).first():
            return error("Remove this course's students and subjects before deleting it.", 409)
        db.session.delete(course)
        result = commit_or_error()
        return result or jsonify({"message": "Course deleted."})
    try:
        data = payload()
        if "name" in data:
            course.name = required_text(data, "name", "Course name", 120)
        if "code" in data:
            course.code = required_text(data, "code", "Course code", 20).upper()
        if "department_id" in data:
            department_id = integer_value(data, "department_id", "Department")
            if db.session.get(Department, department_id) is None:
                return error("Selected department does not exist.")
            if course.students and department_id != course.department_id:
                return error("A course with enrolled students cannot move to another department.", 409)
            course.department_id = department_id
        if "duration_years" in data:
            course.duration_years = integer_value(data, "duration_years", "Duration", 1, 12)
        if "description" in data:
            course.description = optional_text(data, "description", "Description")
    except ValueError as exc:
        return error(str(exc))
    result = commit_or_error()
    return result or jsonify({"course": course.to_dict()})


@bp.route("/subjects", methods=["GET", "POST"])
@require_auth
def subjects():
    if request.method == "GET":
        query = Subject.query
        if request.args.get("course_id"):
            try:
                query = query.filter_by(course_id=int(request.args["course_id"]))
            except ValueError:
                return error("course_id must be a whole number.")
        return jsonify({"subjects": [row.to_dict() for row in query.order_by(Subject.name).all()]})
    try:
        data = payload()
        course_id = integer_value(data, "course_id", "Course")
        if db.session.get(Course, course_id) is None:
            return error("Selected course does not exist.")
        subject = Subject(
            course_id=course_id,
            name=required_text(data, "name", "Subject name", 120),
            code=required_text(data, "code", "Subject code", 24).upper(),
            credits=integer_value(data, "credits", "Credits", 1, 30, 3),
        )
    except ValueError as exc:
        return error(str(exc))
    db.session.add(subject)
    result = commit_or_error()
    return result or (jsonify({"subject": subject.to_dict()}), 201)


@bp.route("/subjects/<int:subject_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def subject_detail(subject_id):
    subject = db.session.get(Subject, subject_id)
    if subject is None:
        return error("Subject not found.", 404)
    if request.method == "GET":
        return jsonify({"subject": subject.to_dict()})
    if request.method == "DELETE":
        db.session.delete(subject)
        result = commit_or_error()
        return result or jsonify({"message": "Subject and associated results deleted."})
    try:
        data = payload()
        if "name" in data:
            subject.name = required_text(data, "name", "Subject name", 120)
        if "code" in data:
            subject.code = required_text(data, "code", "Subject code", 24).upper()
        if "course_id" in data:
            course_id = integer_value(data, "course_id", "Course")
            if db.session.get(Course, course_id) is None:
                return error("Selected course does not exist.")
            subject.course_id = course_id
        if "credits" in data:
            subject.credits = integer_value(data, "credits", "Credits", 1, 30)
    except ValueError as exc:
        return error(str(exc))
    result = commit_or_error()
    return result or jsonify({"subject": subject.to_dict()})


@bp.route("/attendance", methods=["GET", "POST"])
@require_auth
def attendance():
    if request.method == "GET":
        query = Attendance.query.join(Student)
        if request.args.get("student_id"):
            try:
                query = query.filter(Attendance.student_id == int(request.args["student_id"]))
            except ValueError:
                return error("student_id must be a whole number.")
        if request.args.get("date"):
            try:
                chosen_date = parse_date(request.args["date"], "Date", required=True)
            except ValueError as exc:
                return error(str(exc))
            query = query.filter(Attendance.attendance_date == chosen_date)
        if request.args.get("status"):
            if request.args["status"] not in ATTENDANCE_STATUSES:
                return error("Invalid attendance status.")
            query = query.filter(Attendance.status == request.args["status"])
        rows = query.order_by(Attendance.attendance_date.desc(), Student.full_name).limit(500).all()
        return jsonify({"attendance": [row.to_dict() for row in rows]})
    try:
        data = payload()
        student_id = integer_value(data, "student_id", "Student")
        if db.session.get(Student, student_id) is None:
            return error("Selected student does not exist.")
        status = required_text(data, "status", "Attendance status", 20)
        if status not in ATTENDANCE_STATUSES:
            raise ValueError("Choose Present, Absent, Late, or Excused.")
        row = Attendance(
            student_id=student_id,
            attendance_date=parse_date(data.get("attendance_date"), "Attendance date", required=True),
            status=status,
            notes=optional_text(data, "notes", "Notes", 300),
        )
    except ValueError as exc:
        return error(str(exc))
    db.session.add(row)
    result = commit_or_error()
    return result or (jsonify({"attendance": row.to_dict()}), 201)


@bp.route("/attendance/<int:record_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def attendance_detail(record_id):
    row = db.session.get(Attendance, record_id)
    if row is None:
        return error("Attendance record not found.", 404)
    if request.method == "GET":
        return jsonify({"attendance": row.to_dict()})
    if request.method == "DELETE":
        db.session.delete(row)
        result = commit_or_error()
        return result or jsonify({"message": "Attendance record deleted."})
    try:
        data = payload()
        if "student_id" in data:
            student_id = integer_value(data, "student_id", "Student")
            if db.session.get(Student, student_id) is None:
                return error("Selected student does not exist.")
            row.student_id = student_id
        if "attendance_date" in data:
            row.attendance_date = parse_date(data["attendance_date"], "Attendance date", required=True)
        if "status" in data:
            if data["status"] not in ATTENDANCE_STATUSES:
                raise ValueError("Choose Present, Absent, Late, or Excused.")
            row.status = data["status"]
        if "notes" in data:
            row.notes = optional_text(data, "notes", "Notes", 300)
    except ValueError as exc:
        return error(str(exc))
    result = commit_or_error()
    return result or jsonify({"attendance": row.to_dict()})


@bp.route("/results", methods=["GET", "POST"])
@require_auth
def results():
    if request.method == "GET":
        query = Result.query.join(Student).join(Subject)
        for key, column in (("student_id", Result.student_id), ("subject_id", Result.subject_id)):
            if request.args.get(key):
                try:
                    query = query.filter(column == int(request.args[key]))
                except ValueError:
                    return error(f"{key} must be a whole number.")
        return jsonify({"results": [row.to_dict() for row in query.order_by(Result.academic_year.desc(), Student.full_name).limit(1000).all()]})
    try:
        data = payload()
        student_id = integer_value(data, "student_id", "Student")
        subject_id = integer_value(data, "subject_id", "Subject")
        student = db.session.get(Student, student_id)
        subject = db.session.get(Subject, subject_id)
        if student is None or subject is None:
            return error("Selected student or subject does not exist.")
        if student.course_id != subject.course_id:
            return error("The subject must belong to the student's course.")
        max_score_value = data.get("max_score", 100)
        score_value = data.get("score")
        if isinstance(max_score_value, bool) or isinstance(score_value, bool):
            raise ValueError("Score and maximum score must be numbers.")
        max_score = float(max_score_value)
        score = float(score_value)
        if (not isfinite(max_score) or not isfinite(score) or
                not 0 < max_score <= 1000 or not 0 <= score <= max_score):
            raise ValueError("Score must be between zero and the maximum score (up to 1000).")
        year = required_text(data, "academic_year", "Academic year", 20)
        percentage = score / max_score * 100
        grade = "A" if percentage >= 90 else "B" if percentage >= 80 else "C" if percentage >= 70 else "D" if percentage >= 60 else "F"
        row = Result(student_id=student_id, subject_id=subject_id, academic_year=year,
                     score=score, max_score=max_score, grade=grade)
    except (ValueError, TypeError) as exc:
        return error(str(exc) or "Score and maximum score must be numbers.")
    db.session.add(row)
    result = commit_or_error()
    return result or (jsonify({"result": row.to_dict()}), 201)


@bp.route("/results/<int:result_id>", methods=["GET", "PUT", "DELETE"])
@require_auth
def result_detail(result_id):
    row = db.session.get(Result, result_id)
    if row is None:
        return error("Result not found.", 404)
    if request.method == "GET":
        return jsonify({"result": row.to_dict()})
    if request.method == "DELETE":
        db.session.delete(row)
        result = commit_or_error()
        return result or jsonify({"message": "Result deleted."})
    try:
        data = payload()
        student_id = integer_value(
            {"id": data.get("student_id", row.student_id)}, "id", "Student"
        )
        subject_id = integer_value(
            {"id": data.get("subject_id", row.subject_id)}, "id", "Subject"
        )
        student, subject = db.session.get(Student, student_id), db.session.get(Subject, subject_id)
        if student is None or subject is None:
            return error("Selected student or subject does not exist.")
        if student.course_id != subject.course_id:
            return error("The subject must belong to the student's course.")
        score_value = data.get("score", row.score)
        max_score_value = data.get("max_score", row.max_score)
        if isinstance(score_value, bool) or isinstance(max_score_value, bool):
            raise ValueError("Score and maximum score must be numbers.")
        score = float(score_value)
        max_score = float(max_score_value)
        if (not isfinite(max_score) or not isfinite(score) or
                not 0 < max_score <= 1000 or not 0 <= score <= max_score):
            raise ValueError("Score must be between zero and the maximum score (up to 1000).")
        row.student_id, row.subject_id = student_id, subject_id
        row.academic_year = required_text(data, "academic_year", "Academic year", 20) if "academic_year" in data else row.academic_year
        row.score, row.max_score = score, max_score
        percentage = score / max_score * 100
        row.grade = "A" if percentage >= 90 else "B" if percentage >= 80 else "C" if percentage >= 70 else "D" if percentage >= 60 else "F"
    except (ValueError, TypeError) as exc:
        return error(str(exc) or "Score and maximum score must be numbers.")
    result = commit_or_error()
    return result or jsonify({"result": row.to_dict()})

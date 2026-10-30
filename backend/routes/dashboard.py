import csv
from datetime import date, timedelta
from io import StringIO

from flask import Blueprint, Response, jsonify
from sqlalchemy import func

from backend.extensions import db
from backend.models import Attendance, Course, Department, Result, Student
from backend.routes.common import require_auth

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
@require_auth
def dashboard():
    total = Student.query.count()
    active = Student.query.filter_by(status="Active").count()
    today = date.today()
    start = today - timedelta(days=29)
    attendance_counts = dict(
        db.session.query(Attendance.status, func.count(Attendance.id))
        .filter(Attendance.attendance_date >= start, Attendance.attendance_date <= today)
        .group_by(Attendance.status).all()
    )
    result_summary = db.session.query(
        func.avg(Result.score * 100.0 / Result.max_score), func.count(Result.id)
    ).first()
    recent = Student.query.order_by(Student.admission_date.desc(), Student.id.desc()).limit(6).all()
    monthly = []
    for offset in range(5, -1, -1):
        first = today.replace(day=1)
        for _ in range(offset):
            first = (first - timedelta(days=1)).replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        count = Student.query.filter(Student.admission_date >= first, Student.admission_date < next_month).count()
        monthly.append({"month": first.strftime("%b"), "count": count})
    return jsonify({
        "stats": {
            "total_students": total, "active_students": active,
            "inactive_students": Student.query.filter_by(status="Inactive").count(),
            "total_departments": Department.query.count(),
            "total_courses": Course.query.count(),
            "attendance_rate": round(
                attendance_counts.get("Present", 0) * 100 /
                max(sum(attendance_counts.values()), 1), 1
            ),
            "average_score": round(float(result_summary[0] or 0), 1),
            "result_count": result_summary[1] or 0,
            "attendance_records": sum(attendance_counts.values()),
        },
        "attendance": [{"status": key, "count": attendance_counts.get(key, 0)}
                       for key in ("Present", "Absent", "Late", "Excused")],
        "admissions": monthly,
        "recent_admissions": [row.to_dict() for row in recent],
    })


@bp.get("/reports/students.csv")
@require_auth
def students_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID", "Full Name", "Email", "Phone", "Gender", "Date of Birth",
                     "Department", "Course", "Year of Study", "Admission Date", "Status"])
    for student in Student.query.order_by(Student.full_name).all():
        writer.writerow([student.student_id, student.full_name, student.email, student.phone,
                         student.gender, student.date_of_birth or "", student.department.name,
                         student.course.name, student.year_of_study, student.admission_date,
                         student.status])
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=student-report.csv"},
    )

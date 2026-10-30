from datetime import date, datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from backend.extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False, default="Administrator")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "email": self.email, "full_name": self.full_name}


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    students = db.relationship("Student", back_populates="department")
    courses = db.relationship("Course", back_populates="department")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code,
            "description": self.description,
            "student_count": len(self.students), "course_count": len(self.courses),
        }


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    duration_years = db.Column(db.Integer, nullable=False, default=4)
    description = db.Column(db.Text, default="")
    department = db.relationship("Department", back_populates="courses")
    students = db.relationship("Student", back_populates="course")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "code": self.code,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else "",
            "duration_years": self.duration_years, "description": self.description,
            "student_count": len(self.students),
        }


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(32), nullable=False, default="")
    gender = db.Column(db.String(20), nullable=False, default="Prefer not to say")
    date_of_birth = db.Column(db.Date, nullable=True)
    address = db.Column(db.Text, default="")
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    year_of_study = db.Column(db.Integer, nullable=False, default=1)
    admission_date = db.Column(db.Date, nullable=False, default=date.today)
    profile_photo = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    department = db.relationship("Department", back_populates="students")
    course = db.relationship("Course", back_populates="students")
    attendance = db.relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    results = db.relationship("Result", back_populates="student", cascade="all, delete-orphan")

    def to_dict(self, include_records=False):
        data = {
            "id": self.id, "student_id": self.student_id, "full_name": self.full_name,
            "email": self.email, "phone": self.phone, "gender": self.gender,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else "",
            "address": self.address, "department_id": self.department_id,
            "department_name": self.department.name if self.department else "",
            "course_id": self.course_id, "course_name": self.course.name if self.course else "",
            "year_of_study": self.year_of_study,
            "admission_date": self.admission_date.isoformat() if self.admission_date else "",
            "profile_photo": self.profile_photo or "", "status": self.status,
        }
        if include_records:
            data["attendance"] = [row.to_dict() for row in self.attendance]
            data["results"] = [row.to_dict() for row in self.results]
        return data


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.String(300), default="")
    student = db.relationship("Student", back_populates="attendance")
    __table_args__ = (db.UniqueConstraint("student_id", "attendance_date", name="uq_attendance_student_date"),)

    def to_dict(self):
        return {
            "id": self.id, "student_id": self.student_id,
            "student_number": self.student.student_id if self.student else "",
            "student_name": self.student.full_name if self.student else "",
            "attendance_date": self.attendance_date.isoformat(), "status": self.status,
            "notes": self.notes or "",
        }


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(24), nullable=False)
    credits = db.Column(db.Integer, nullable=False, default=3)
    course = db.relationship("Course")
    results = db.relationship("Result", back_populates="subject", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("course_id", "code", name="uq_subject_course_code"),)

    def to_dict(self):
        return {
            "id": self.id, "course_id": self.course_id,
            "course_name": self.course.name if self.course else "",
            "name": self.name, "code": self.code, "credits": self.credits,
        }


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False, index=True)
    academic_year = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, nullable=False, default=100)
    grade = db.Column(db.String(4), nullable=False)
    student = db.relationship("Student", back_populates="results")
    subject = db.relationship("Subject", back_populates="results")
    __table_args__ = (db.UniqueConstraint("student_id", "subject_id", "academic_year", name="uq_result_student_subject_year"),)

    def to_dict(self):
        return {
            "id": self.id, "student_id": self.student_id,
            "student_number": self.student.student_id if self.student else "",
            "student_name": self.student.full_name if self.student else "",
            "subject_id": self.subject_id, "subject_name": self.subject.name if self.subject else "",
            "subject_code": self.subject.code if self.subject else "",
            "academic_year": self.academic_year, "score": self.score,
            "max_score": self.max_score, "grade": self.grade,
        }

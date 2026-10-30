import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from backend.application import create_app
from backend.config import database_url


class ApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "integration-test-secret",
            "ADMIN_EMAIL": "test-admin@example.com",
            "ADMIN_PASSWORD": "test-password",
        })
        cls.client = cls.app.test_client()

    def test_authenticated_crud_validation_dashboard_and_csv_lifecycle(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/api/students").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/students",
                headers={"Authorization": "Bearer invalid-token"},
            ).status_code,
            401,
        )
        bad_login = self.client.post(
            "/api/auth/login",
            json={"email": "test-admin@example.com", "password": "wrong"},
        )
        self.assertEqual(bad_login.status_code, 401)
        login = self.client.post(
            "/api/auth/login",
            json={"email": "test-admin@example.com", "password": "test-password"},
        )
        self.assertEqual(login.status_code, 200)
        headers = {"Authorization": f"Bearer {login.json['token']}"}
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)

        def request(method, path, body=None, expected=200):
            response = getattr(self.client, method)(
                path, json=body, headers=headers
            )
            self.assertEqual(response.status_code, expected, response.get_data(as_text=True))
            return response

        department = request(
            "post", "/api/departments",
            {"name": "Engineering", "code": "ENG"},
            201,
        ).json["department"]
        self.assertEqual(
            request("get", f"/api/departments/{department['id']}").json["department"]["code"],
            "ENG",
        )
        self.assertEqual(
            request("put", f"/api/departments/{department['id']}", {"description": "Updated"})
            .json["department"]["description"],
            "Updated",
        )
        self.assertEqual(
            request("get", "/api/departments").json["departments"][0]["id"],
            department["id"],
        )
        course = request(
            "post", "/api/courses",
            {"name": "Computing", "code": "CS", "department_id": department["id"]},
            201,
        ).json["course"]
        self.assertEqual(
            request("get", f"/api/courses/{course['id']}").json["course"]["code"],
            "CS",
        )
        self.assertEqual(
            request("get", f"/api/courses?department_id={department['id']}")
            .json["courses"][0]["id"],
            course["id"],
        )
        self.assertEqual(
            request("put", f"/api/courses/{course['id']}", {"duration_years": 3})
            .json["course"]["duration_years"],
            3,
        )
        request("post", "/api/courses", {"name": "Missing department", "code": "BAD", "department_id": 999}, 400)
        request("post", "/api/courses", {"name": "Fractional duration", "code": "FRA", "department_id": department["id"], "duration_years": 1.5}, 400)
        subject = request(
            "post", "/api/subjects",
            {"course_id": course["id"], "name": "Programming", "code": "CS101"},
            201,
        ).json["subject"]
        self.assertEqual(
            request("get", f"/api/subjects/{subject['id']}").json["subject"]["code"],
            "CS101",
        )
        self.assertEqual(
            request("get", f"/api/subjects?course_id={course['id']}")
            .json["subjects"][0]["id"],
            subject["id"],
        )
        self.assertEqual(
            request("put", f"/api/subjects/{subject['id']}", {"credits": 4})
            .json["subject"]["credits"],
            4,
        )
        request("post", "/api/subjects", {"course_id": 999, "name": "Invalid", "code": "NOPE"}, 400)
        student = request(
            "post", "/api/students",
            {
                "student_id": "STU-001",
                "full_name": "Jordan Taylor",
                "email": "jordan@example.edu",
                "department_id": department["id"],
                "course_id": course["id"],
                "year_of_study": 1,
                "admission_date": "2020-08-15",
            },
            201,
        ).json["student"]

        request("post", "/api/students", [], 400)
        request(
            "post", "/api/students",
            {
                "student_id": "STU-OTHER", "full_name": "Duplicate email",
                "email": "jordan@example.edu", "department_id": department["id"],
                "course_id": course["id"], "admission_date": "2020-08-15",
            },
            409,
        )
        request(
            "post", "/api/students",
            {
                "student_id": "STU-BAD", "full_name": "Invalid Email",
                "email": "not-an-email", "department_id": department["id"],
                "course_id": course["id"], "admission_date": "2020-08-15",
            },
            400,
        )
        request("get", "/api/students?department_id=invalid", None, 400)
        request("get", "/api/students?status=unknown", None, 400)
        self.assertEqual(
            request("get", f"/api/students?department_id={department['id']}&course_id={course['id']}&status=Active")
            .json["total"],
            1,
        )
        request("delete", f"/api/departments/{department['id']}", None, 409)
        request("delete", f"/api/courses/{course['id']}", None, 409)

        other_department = request(
            "post", "/api/departments",
            {"name": "Science", "code": "SCI"},
            201,
        ).json["department"]
        request(
            "put", f"/api/students/{student['id']}",
            {"department_id": other_department["id"]},
            400,
        )
        request("delete", f"/api/departments/{other_department['id']}")

        self.assertEqual(request("get", "/api/students?search=Jordan").json["total"], 1)
        self.assertEqual(
            request("get", f"/api/students/{student['id']}").json["student"]["student_id"],
            "STU-001",
        )
        self.assertEqual(
            request("put", f"/api/students/{student['id']}", {"year_of_study": 2})
            .json["student"]["year_of_study"],
            2,
        )
        attendance = request(
            "post", "/api/attendance",
            {"student_id": student["id"], "attendance_date": date.today().isoformat(), "status": "Present"},
            201,
        ).json["attendance"]
        self.assertEqual(
            request("get", f"/api/attendance/{attendance['id']}").json["attendance"]["status"],
            "Present",
        )
        self.assertEqual(
            len(request(
                "get",
                f"/api/attendance?student_id={student['id']}&date={date.today().isoformat()}&status=Present",
            ).json["attendance"]),
            1,
        )
        request("get", "/api/attendance?date=not-a-date", None, 400)
        request("get", "/api/attendance?status=unknown", None, 400)
        request(
            "post", "/api/attendance",
            {"student_id": student["id"], "attendance_date": date.today().isoformat(), "status": "Present"},
            409,
        )
        self.assertEqual(
            request("put", f"/api/attendance/{attendance['id']}", {"status": "Late"})
            .json["attendance"]["status"],
            "Late",
        )
        request("put", f"/api/attendance/{attendance['id']}", {"status": "Not a status"}, 400)
        temporary_attendance = request(
            "post", "/api/attendance",
            {
                "student_id": student["id"],
                "attendance_date": (date.today() - timedelta(days=1)).isoformat(),
                "status": "Absent",
            },
            201,
        ).json["attendance"]
        self.assertEqual(
            request("delete", f"/api/attendance/{temporary_attendance['id']}").status_code,
            200,
        )
        request("get", f"/api/attendance/{temporary_attendance['id']}", None, 404)

        result = request(
            "post", "/api/results",
            {
                "student_id": student["id"], "subject_id": subject["id"],
                "academic_year": "2026-2027", "score": 94, "max_score": 100,
            },
            201,
        ).json["result"]
        self.assertEqual(result["grade"], "A")
        self.assertEqual(
            request("get", f"/api/results/{result['id']}").json["result"]["grade"],
            "A",
        )
        self.assertEqual(
            len(request(
                "get",
                f"/api/results?student_id={student['id']}&subject_id={subject['id']}",
            ).json["results"]),
            1,
        )
        request(
            "post", "/api/results",
            {
                "student_id": student["id"], "subject_id": subject["id"],
                "academic_year": "2026-2027", "score": "NaN",
            },
            400,
        )
        request(
            "post", "/api/results",
            {
                "student_id": student["id"], "subject_id": subject["id"],
                "academic_year": "2026-2027", "score": 94,
            },
            409,
        )
        request("get", "/api/results?student_id=invalid", None, 400)
        request("put", f"/api/results/{result['id']}", {"score": True}, 400)
        for score, expected_grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D"), (59, "F"), (0, "F")):
            updated = request("put", f"/api/results/{result['id']}", {"score": score})
            self.assertEqual(updated.json["result"]["grade"], expected_grade)
        temporary_result = request(
            "post", "/api/results",
            {
                "student_id": student["id"], "subject_id": subject["id"],
                "academic_year": "2025-2026", "score": 88,
            },
            201,
        ).json["result"]
        self.assertEqual(
            request("delete", f"/api/results/{temporary_result['id']}").status_code,
            200,
        )
        request("get", f"/api/results/{temporary_result['id']}", None, 404)
        self.assertEqual(
            request("put", f"/api/results/{result['id']}", {"score": 71})
            .json["result"]["grade"],
            "C",
        )
        dashboard = request("get", "/api/dashboard").json
        self.assertEqual(dashboard["stats"]["total_students"], 1)
        self.assertEqual(dashboard["stats"]["active_students"], 1)
        self.assertEqual(dashboard["stats"]["total_departments"], 1)
        self.assertEqual(dashboard["stats"]["total_courses"], 1)
        self.assertEqual(dashboard["stats"]["attendance_rate"], 0)
        self.assertEqual(dashboard["stats"]["average_score"], 71)
        self.assertEqual(dashboard["stats"]["attendance_records"], 1)
        self.assertEqual(len(dashboard["admissions"]), 6)
        expected_months = []
        month = date.today().replace(day=1)
        for _ in range(5):
            month = (month - timedelta(days=1)).replace(day=1)
        for _ in range(6):
            expected_months.append(month.strftime("%b"))
            month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        self.assertEqual(
            [entry["month"] for entry in dashboard["admissions"]],
            expected_months,
        )
        csv_response = request("get", "/api/reports/students.csv")
        self.assertIn("text/csv", csv_response.content_type)
        self.assertIn("STU-001", csv_response.get_data(as_text=True))

        request("delete", f"/api/students/{student['id']}")
        request("get", f"/api/students/{student['id']}", None, 404)
        self.assertEqual(request("get", "/api/attendance").json["attendance"], [])
        self.assertEqual(request("get", "/api/results").json["results"], [])
        request("delete", f"/api/subjects/{subject['id']}")
        request("delete", f"/api/courses/{course['id']}")
        request("delete", f"/api/departments/{department['id']}")
        request("get", f"/api/departments/{department['id']}", None, 404)
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        page = self.client.get("/students.html")
        script = self.client.get("/static/js/app.js")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        page.close()
        script.close()

    def test_public_admin_signup_validates_and_authenticates_new_account(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "New Campus Admin",
                "email": " New.Admin@example.com ",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(response.json["user"]["email"], "new.admin@example.com")
        self.assertEqual(response.json["user"]["full_name"], "New Campus Admin")
        self.assertTrue(response.json["token"])

        login = self.client.post(
            "/api/auth/login",
            json={
                "email": "new.admin@example.com",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(login.status_code, 200)

        duplicate = self.client.post(
            "/api/auth/register",
            json={
                "full_name": "Duplicate Admin",
                "email": "NEW.ADMIN@example.com",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        invalid_requests = (
            ({"full_name": "Short pass", "email": "short@example.com", "password": "short"}, 400),
            ({"full_name": "Bad email", "email": "not-an-email", "password": "secure-password"}, 400),
            ({"full_name": "  ", "email": "missing@example.com", "password": "secure-password"}, 400),
        )
        for body, expected_status in invalid_requests:
            with self.subTest(body=body):
                result = self.client.post("/api/auth/register", json=body)
                self.assertEqual(result.status_code, expected_status)

    def test_all_frontend_pages_and_assets_are_served(self):
        pages = (
            "index", "login", "students", "departments",
            "courses", "attendance", "results", "reports",
        )
        for page_name in pages:
            with self.subTest(page=page_name):
                response = self.client.get(f"/{page_name}.html")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"CampusCore", response.get_data())
                response.close()

        for asset_path in (
            "/static/css/app.css",
            "/static/js/app.js",
            "/static/js/login.js",
        ):
            with self.subTest(asset=asset_path):
                response = self.client.get(asset_path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_postman_collection_covers_all_resource_crud_methods(self):
        collection_path = (
            Path(__file__).resolve().parents[1]
            / "backend" / "postman" / "student_management_collection.json"
        )
        collection = json.loads(collection_path.read_text(encoding="utf-8"))
        methods_by_path = {}

        def collect(items):
            for item in items:
                if "request" not in item:
                    collect(item.get("item", []))
                    continue
                request = item["request"]
                raw_url = request["url"]["raw"]
                path = raw_url.split("?", 1)[0].replace("{{baseUrl}}", "")
                methods_by_path.setdefault(path, set()).add(request["method"])

        collect(collection["item"])
        singular = {
            "students": "student",
            "departments": "department",
            "courses": "course",
            "subjects": "subject",
            "attendance": "attendance",
            "results": "result",
        }
        for resource, item_name in singular.items():
            collection_methods = methods_by_path.get(f"/api/{resource}", set())
            detail_methods = methods_by_path.get(f"/api/{resource}/{{{{{item_name}Id}}}}", set())
            with self.subTest(resource=resource):
                self.assertTrue({"GET", "POST"} <= collection_methods)
                self.assertTrue({"GET", "PUT", "DELETE"} <= detail_methods)
        self.assertIn("GET", methods_by_path["/api/dashboard"])
        self.assertIn("GET", methods_by_path["/api/reports/students.csv"])
        self.assertIn("POST", methods_by_path["/api/auth/register"])

    def test_database_url_defaults_to_sqlite_and_normalizes_postgres(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(database_url(), "sqlite:///student_management.db")
        with patch.dict("os.environ", {"DATABASE_URL": "postgres://user:pass@db.example/app"}):
            self.assertEqual(
                database_url(),
                "postgresql+psycopg://user:pass@db.example/app",
            )
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:pass@db.example/app"}):
            self.assertEqual(
                database_url(),
                "postgresql+psycopg://user:pass@db.example/app",
            )

    def test_first_run_requires_admin_password(self):
        with self.assertRaisesRegex(RuntimeError, "Set ADMIN_PASSWORD"):
            create_app({
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SECRET_KEY": "test-secret",
                "ADMIN_EMAIL": "no-password@example.com",
                "ADMIN_PASSWORD": None,
            })


if __name__ == "__main__":
    unittest.main()

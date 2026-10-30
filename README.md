# CampusCore Student Management System

A responsive student administration application built with HTML, CSS, vanilla JavaScript, Flask REST APIs, SQLAlchemy, and SQLite/PostgreSQL. The Flask server hosts the frontend and API on the same origin; no frontend build step or CORS configuration is needed.

## Features

- Admin sign-in and sign-out using time-limited, signed bearer tokens.
- Student profiles with search, department/course/status filters, edit, profile view, and delete.
- Department, course, and subject catalog management.
- Attendance entry, filtering, updates, and deletion, with one record per student per day.
- Results entry with course/subject validation and automatic grades (A: 90+, B: 80+, C: 70+, D: 60+, F: below 60).
- Database-backed dashboard statistics, attendance summary, admissions chart, and academic performance.
- Student CSV export and a Postman collection covering the API.
- Responsive layouts for desktop and mobile.

## Requirements

- Python 3.10 or later
- Visual Studio Code (recommended)
- Postman (for API testing)

## Run locally (Windows / VS Code terminal)

From the folder containing `student-management-system`:

```powershell
cd .\student-management-system
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and set a private `SECRET_KEY` and a strong `ADMIN_PASSWORD` before starting the application. The app will not create its first administrator if `ADMIN_PASSWORD` is empty. Generate a secret with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the generated value into `SECRET_KEY`, choose an administrator password, and keep `.env` private and untracked. The first-run administrator uses the configured `ADMIN_EMAIL` and `ADMIN_PASSWORD`.

Start the server:

```powershell
python app.py
```

Visit <http://127.0.0.1:5000/> and sign in. The SQLite database is created automatically in `instance/student_management.db`; tables and the initial administrator are also created on the first run. Stop the server with `Ctrl+C`.

Run the included integration test suite with:

```powershell
python -m unittest discover -s tests -v
```

The suite exercises authentication, CRUD for every resource, invalid and duplicate data, filtering, cascading deletes, dashboard/CSV output, all served pages/assets, PostgreSQL URL normalization, initial-admin setup, and Postman collection coverage.

If PowerShell blocks venv activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate the environment again. For a development server with Flask's CLI instead, run `$env:FLASK_APP = "app.py"; flask run`.

### Local configuration

| Variable | Local behavior |
|---|---|
| `SECRET_KEY` | Signs authentication tokens. Set a random private value in `.env`. |
| `ADMIN_EMAIL` | Email for the first-run administrator; defaults to `admin@example.com`. |
| `ADMIN_PASSWORD` | Required password for the first-run administrator; keep it private in `.env`. |
| `DATABASE_URL` | Leave unset to use SQLite. |
| `PORT` | Local server port; defaults to `5000`. |

The administrator is seeded only if that email does not already exist. Changing these variables later does not change an existing account's password.

## REST API

All API routes use the `/api` prefix. Except `POST /api/auth/login`, routes require:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

| Area | Routes |
|---|---|
| Authentication | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Students | `GET/POST /api/students`, `GET/PUT/DELETE /api/students/{id}` |
| Departments | `GET/POST /api/departments`, `GET/PUT/DELETE /api/departments/{id}` |
| Courses | `GET/POST /api/courses`, `GET/PUT/DELETE /api/courses/{id}` |
| Subjects | `GET/POST /api/subjects`, `GET/PUT/DELETE /api/subjects/{id}` |
| Attendance | `GET/POST /api/attendance`, `GET/PUT/DELETE /api/attendance/{id}` |
| Results | `GET/POST /api/results`, `GET/PUT/DELETE /api/results/{id}` |
| Dashboard | `GET /api/dashboard` |
| Reports | `GET /api/reports/students.csv` |

Student list filters: `search`, `department_id`, `course_id`, and `status`. Courses support `department_id`; attendance supports `student_id`, `date`, and `status`; results support `student_id` and `subject_id`. Unique IDs, emails, department/course codes, attendance student/date pairs, and result student/subject/academic-year combinations are enforced. Deleting a student removes their attendance and results; deleting a department/course with dependent records is rejected with a helpful `409`.

## Test with Postman

1. Start the app and open Postman.
2. Select **Import** and choose `backend/postman/student_management_collection.json`.
3. Open the collection's **Variables** tab. Set `baseUrl` to `http://127.0.0.1:5000`, `adminEmail` to the configured admin email, and `adminPassword` to its password.
4. Run requests in collection order with the Collection Runner. The login request stores the token; create requests save department, course, subject, student, attendance, and result IDs for the later requests.
5. The collection asserts expected status codes, includes request/response examples, and exercises create/read/update/delete, authentication, filtering, and CSV export. Use a fresh local database (or remove only the app's `instance/student_management.db` while the server is stopped) before repeating the entire create/delete scenario.

The sign-in page also offers public administrator registration. `POST /api/auth/register` accepts `full_name`, `email`, and a password of at least 8 characters, then returns a signed token so the new account can continue directly to the dashboard. Because registration is public, anyone able to reach the deployment can create an administrator account; restrict network access or disable public registration before exposing a production deployment if that is not intended.

For a quick manual check, send `POST /api/auth/login` with the email and password configured in `.env`. Copy `token` from the response into a Bearer Token authorization header for the other routes.

## Deploy to Render

1. Push this project to a GitHub repository. If the repository contains other projects, set Render's **Root Directory** to `student-management-system`.
2. In Render, create a managed **PostgreSQL** database. Copy its **Internal Database URL** for the web service.
3. Create a **Web Service** from the repository. Set:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn --bind 0.0.0.0:$PORT backend.app:app`
4. In the web service's **Environment** settings, add:
   - `DATABASE_URL` — the PostgreSQL Internal Database URL from step 2.
   - `SECRET_KEY` — a newly generated, long random value (do not reuse a checked-in value).
   - `ADMIN_EMAIL` — your administrator email.
   - `ADMIN_PASSWORD` — a unique, strong password.
5. Deploy. The app normalizes Render's `postgres://` URL to the Psycopg SQLAlchemy driver, creates the schema on startup, and uses the managed PostgreSQL database. Open the generated Render URL and sign in.
6. Confirm `/health` returns `{"status":"ok"}` and test sign-in/API operations. Keep database and admin credentials only in Render's environment settings; never put them in source control.

Render's local filesystem is ephemeral; use the managed PostgreSQL database for deployed data. `requirements.txt` includes Gunicorn and the Psycopg 3 binary driver; `Procfile` binds Gunicorn to Render's assigned port.

## Project layout

```text
student-management-system/
├── app.py
├── backend/
│   ├── app.py
│   ├── application.py
│   ├── config.py
│   ├── extensions.py
│   ├── models.py
│   ├── routes/
│   └── postman/student_management_collection.json
├── frontend/
│   ├── index.html, login.html, students.html, departments.html
│   ├── courses.html, attendance.html, results.html, reports.html
│   ├── css/app.css
│   └── js/app.js, login.js
├── .env.example
├── .gitignore
├── Procfile
└── requirements.txt
```

(() => {
  const token = localStorage.getItem("campuscore_token");
  if (!token) {
    window.location.replace("/login.html");
    return;
  }

  const page = document.body.dataset.page;
  const state = { students: [], departments: [], courses: [], subjects: [], attendance: [], results: [], dashboard: null };
  const today = new Date();
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const isoToday = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  async function api(url, options = {}) {
    const headers = { Authorization: `Bearer ${token}`, ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401) {
      localStorage.removeItem("campuscore_token");
      localStorage.removeItem("campuscore_user");
      window.location.replace("/login.html");
      throw new Error("Your session has expired. Sign in again.");
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `Request failed (${response.status}).`);
    }
    return response;
  }

  async function getJson(url) {
    return (await api(url)).json();
  }

  async function sendJson(url, method, data) {
    const response = await api(url, { method, body: JSON.stringify(data) });
    return response.status === 204 ? {} : response.json();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function toast(message, isError = false) {
    const root = $("#toast-root");
    const node = document.createElement("div");
    node.className = `toast${isError ? " error" : ""}`;
    node.textContent = message;
    root.append(node);
    window.setTimeout(() => node.remove(), 3700);
  }

  function showLoading(selector) {
    const node = $(selector);
    if (node) node.innerHTML = '<div class="loading"><span class="spinner"></span>Loading records…</div>';
  }

  function showError(selector, message) {
    const node = $(selector);
    if (node) node.innerHTML = `<div class="empty-state"><div class="empty-icon">!</div><b>Could not load this section</b><p>${escapeHtml(message)}</p></div>`;
  }

  function formatDate(value) {
    if (!value) return "—";
    const parsed = new Date(`${value}T00:00:00`);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }

  function initials(name) {
    return String(name || "?").trim().split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
  }

  function badge(status) {
    const safe = String(status || "").toLowerCase().replace(/[^a-z-]/g, "");
    return `<span class="badge badge-${safe}">${escapeHtml(status || "Unknown")}</span>`;
  }

  function empty(icon, title, detail) {
    return `<div class="empty-state"><div class="empty-icon">${icon}</div><b>${escapeHtml(title)}</b><p>${escapeHtml(detail)}</p></div>`;
  }

  function setUser(user) {
    const name = user?.full_name || "Administrator";
    if ($("#user-name")) $("#user-name").textContent = name;
    if ($("#user-email")) $("#user-email").textContent = user?.email || "";
    if ($("#user-avatar")) $("#user-avatar").textContent = initials(name);
    $$(".avatar-small").forEach((el) => { el.textContent = initials(name); });
    if ($("#today-label")) $("#today-label").textContent = today.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  }

  function setOptions(selector, items, label, valueKey = "id", textKey = "name", selected = "") {
    const select = $(selector);
    if (!select) return;
    const firstOption = select.querySelector("option")?.outerHTML || `<option value="">${escapeHtml(label)}</option>`;
    select.innerHTML = firstOption + items.map((item) =>
      `<option value="${escapeHtml(item[valueKey])}"${String(item[valueKey]) === String(selected) ? " selected" : ""}>${escapeHtml(item[textKey])}</option>`
    ).join("");
  }

  function navEvents() {
    $$(".logout-button").forEach((button) => button.addEventListener("click", async () => {
      try { await sendJson("/api/auth/logout", "POST", {}); }
      catch (error) { console.error(error); }
      localStorage.removeItem("campuscore_token");
      localStorage.removeItem("campuscore_user");
      window.location.replace("/login.html");
    }));
    $(".menu-button")?.addEventListener("click", () => $(".sidebar")?.classList.toggle("open"));
    document.addEventListener("click", (event) => {
      const sidebar = $(".sidebar");
      if (sidebar?.classList.contains("open") && !sidebar.contains(event.target) && !event.target.closest(".menu-button")) sidebar.classList.remove("open");
    });
  }

  function actionEvents() {
    document.addEventListener("click", async (event) => {
      const action = event.target.closest("[data-action]");
      if (action) {
        event.preventDefault();
        const type = action.dataset.action;
        if (type === "create-student") openForm("student");
        else if (type === "create-department") openForm("department");
        else if (type === "create-course") openForm("course");
        else if (type === "create-subject") openForm("subject");
        else if (type === "create-attendance") openForm("attendance");
        else if (type === "create-result") openForm("result");
        else if (type === "export-students") downloadCsv();
        return;
      }
      const view = event.target.closest("[data-view-student]");
      if (view) return viewStudent(view.dataset.viewStudent);
      const edit = event.target.closest("[data-edit]");
      if (edit) return openForm(edit.dataset.edit, edit.dataset.id);
      const del = event.target.closest("[data-delete]");
      if (del) return deleteRecord(del.dataset.delete, del.dataset.id);
    });
  }

  function bindFilters() {
    $("#student-search")?.addEventListener("input", renderStudents);
    $("#department-filter")?.addEventListener("change", () => {
      const departmentId = $("#department-filter").value;
      setOptions("#course-filter", state.courses.filter((course) => !departmentId || String(course.department_id) === departmentId), "All courses");
      renderStudents();
    });
    $("#course-filter")?.addEventListener("change", renderStudents);
    $("#status-filter")?.addEventListener("change", renderStudents);
    $("#attendance-search")?.addEventListener("input", renderAttendance);
    $("#attendance-date-filter")?.addEventListener("change", renderAttendance);
    $("#attendance-status-filter")?.addEventListener("change", renderAttendance);
    $("#results-search")?.addEventListener("input", renderResults);
    $("#results-student-filter")?.addEventListener("change", renderResults);
    $("#results-subject-filter")?.addEventListener("change", renderResults);
    $$("[data-tab]").forEach((button) => button.addEventListener("click", () => {
      $$("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
      const subjects = button.dataset.tab === "subjects";
      $("#courses-grid").hidden = subjects;
      $("#courses-summary").hidden = subjects;
      $("#subjects-panel").hidden = !subjects;
    }));
  }

  function statCard(label, value, icon, tone, foot) {
    return `<article class="stat-card" style="--stat-color:${tone};--stat-soft:${tone}18"><div class="stat-top"><span>${escapeHtml(label)}</span><span class="stat-icon">${icon}</span></div><div class="stat-value">${escapeHtml(value)}</div><div class="stat-foot">${escapeHtml(foot)}</div></article>`;
  }

  async function loadDashboard() {
    for (const selector of ["#dashboard-stats", "#attendance-summary", "#recent-students", "#performance-summary"]) showLoading(selector);
    try {
      state.dashboard = await getJson("/api/dashboard");
      renderDashboard();
      if (page === "reports") renderReports();
    } catch (error) {
      showError("#dashboard-stats", error.message);
      if (page === "reports") showError("#report-stats", error.message);
    }
  }

  function renderDashboard() {
    const { stats, attendance, admissions, recent_admissions: recent } = state.dashboard;
    if ($("#dashboard-stats")) {
      $("#dashboard-stats").innerHTML = [
        statCard("Total students", stats.total_students, "♙", "#6374df", "Enrolled across all programs"),
        statCard("Active students", stats.active_students, "✓", "#35ad89", `${stats.inactive_students} inactive students`),
        statCard("Departments", stats.total_departments, "▦", "#e5a545", `${stats.total_courses} courses offered`),
        statCard("Attendance rate", `${stats.attendance_rate}%`, "◷", "#8c78d8", "Present in the last 30 days"),
      ].join("");
    }
    if ($("#attendance-summary")) {
      const total = attendance.reduce((sum, item) => sum + item.count, 0);
      const colors = { Present: "#39b58c", Absent: "#e47b82", Late: "#e7aa4e", Excused: "#7887df" };
      $("#attendance-summary").innerHTML = total ? attendance.map((item) => {
        const percent = Math.round(item.count * 100 / total);
        return `<div class="attendance-line"><span>${escapeHtml(item.status)}</span><div class="progress-track"><div class="progress-fill" style="--fill:${colors[item.status]};width:${percent}%"></div></div><b>${percent}%</b></div>`;
      }).join("") : empty("◷", "No attendance yet", "Record attendance to see a 30-day snapshot.");
    }
    if ($("#recent-students")) {
      $("#recent-students").innerHTML = recent.length ? recent.map((student) =>
        `<div class="recent-row"><span class="mini-avatar">${escapeHtml(initials(student.full_name))}</span><span class="recent-name"><b>${escapeHtml(student.full_name)}</b><small>${escapeHtml(student.student_id)}</small></span><span class="recent-course">${escapeHtml(student.course_name)}</span><span class="recent-date">${formatDate(student.admission_date)}</span></div>`
      ).join("") : empty("♙", "No admissions yet", "Your newest student profiles will appear here.");
    }
    if ($("#performance-summary")) {
      const score = Math.min(100, Number(stats.average_score) || 0);
      $("#performance-summary").innerHTML = `<div class="performance-ring" style="--progress:${score}%"><span>${score}%</span></div><div class="performance-meta"><b>${stats.result_count ? "Average score" : "No results yet"}</b><p>${stats.result_count ? `${stats.result_count} result${stats.result_count === 1 ? "" : "s"} recorded across all subjects.` : "Add student results to track academic performance."}</p></div>`;
    }
    drawAdmissions(admissions);
  }

  function drawAdmissions(data) {
    const canvas = $("#admissions-chart");
    if (!canvas) return;
    const box = canvas.getBoundingClientRect();
    if (!box.width || !box.height) return;
    const scale = window.devicePixelRatio || 1;
    canvas.width = box.width * scale;
    canvas.height = box.height * scale;
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    const width = box.width, height = box.height;
    const left = 26, right = 12, top = 14, bottom = 27;
    const plotHeight = height - top - bottom, plotWidth = width - left - right;
    const values = data.map((item) => item.count);
    const max = Math.max(4, ...values);
    ctx.font = "10px DM Sans, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.strokeStyle = "#eef0f4";
    ctx.fillStyle = "#a0aaba";
    for (let i = 0; i < 4; i += 1) {
      const y = top + plotHeight * i / 3;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
      ctx.fillText(String(Math.round(max * (3 - i) / 3)), left - 7, y);
    }
    const points = data.map((item, index) => ({
      x: left + (data.length < 2 ? plotWidth / 2 : plotWidth * index / (data.length - 1)),
      y: top + plotHeight * (1 - item.count / max),
    }));
    const gradient = ctx.createLinearGradient(0, top, 0, height - bottom);
    gradient.addColorStop(0, "rgba(91, 109, 228, .19)");
    gradient.addColorStop(1, "rgba(91, 109, 228, 0)");
    ctx.beginPath();
    points.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
    if (points.length) {
      ctx.lineTo(points[points.length - 1].x, height - bottom);
      ctx.lineTo(points[0].x, height - bottom);
      ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
    }
    ctx.beginPath();
    points.forEach((point, index) => index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y));
    ctx.strokeStyle = "#6676e8"; ctx.lineWidth = 2.3; ctx.lineJoin = "round"; ctx.stroke();
    points.forEach((point, index) => {
      ctx.beginPath(); ctx.arc(point.x, point.y, 3.2, 0, Math.PI * 2); ctx.fillStyle = "#fff"; ctx.fill();
      ctx.strokeStyle = "#6676e8"; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = "#929eb0"; ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.fillText(data[index].month, point.x, height - bottom + 9);
    });
  }

  async function loadStudents() {
    showLoading("#students-table");
    try {
      const [studentData, departments, courses] = await Promise.all([
        getJson("/api/students"), getJson("/api/departments"), getJson("/api/courses"),
      ]);
      state.students = studentData.students;
      state.departments = departments.departments;
      state.courses = courses.courses;
      setOptions("#department-filter", state.departments, "All departments");
      setOptions("#course-filter", state.courses, "All courses");
      renderStudents();
    } catch (error) { showError("#students-table", error.message); }
  }

  function renderStudents() {
    if (!$("#students-table")) return;
    const search = ($("#student-search")?.value || "").trim().toLowerCase();
    const dept = $("#department-filter")?.value || "";
    const course = $("#course-filter")?.value || "";
    const status = $("#status-filter")?.value || "";
    const rows = state.students.filter((student) =>
      (!search || [student.full_name, student.student_id, student.email].some((value) => value.toLowerCase().includes(search))) &&
      (!dept || String(student.department_id) === dept) &&
      (!course || String(student.course_id) === course) &&
      (!status || student.status === status)
    );
    if ($("#students-summary")) $("#students-summary").innerHTML = `<strong>${rows.length}</strong> student${rows.length === 1 ? "" : "s"} shown <span>·</span> ${state.students.length} total`;
    $("#students-table").innerHTML = rows.length ? `<table><thead><tr><th>Student</th><th>Student ID</th><th>Department / course</th><th>Year</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows.map((student) => `<tr><td><div class="table-person"><span class="mini-avatar">${escapeHtml(initials(student.full_name))}</span><span><b>${escapeHtml(student.full_name)}</b><small>${escapeHtml(student.email)}</small></span></div></td><td class="table-id">${escapeHtml(student.student_id)}</td><td>${escapeHtml(student.department_name)}<small class="cell-subtext">${escapeHtml(student.course_name)}</small></td><td>Year ${student.year_of_study}</td><td>${badge(student.status)}</td><td><div class="row-actions"><button class="table-action" data-view-student="${student.id}" title="View profile" aria-label="View profile">◉</button><button class="table-action" data-edit="student" data-id="${student.id}" title="Edit student" aria-label="Edit student">✎</button><button class="table-action delete" data-delete="student" data-id="${student.id}" title="Delete student" aria-label="Delete student">×</button></div></td></tr>`).join("")}</tbody></table>` : empty("♙", "No students found", search || dept || course || status ? "Try changing the search or filters." : "Add your first student to get started.");
  }

  async function loadDepartments() {
    showLoading("#departments-grid");
    try {
      const data = await getJson("/api/departments");
      state.departments = data.departments;
      $("#departments-summary").innerHTML = `<strong>${state.departments.length}</strong> department${state.departments.length === 1 ? "" : "s"} in your institution`;
      $("#departments-grid").innerHTML = state.departments.length ? state.departments.map((dept) => `<article class="entity-card"><div class="entity-card-top"><span class="entity-icon">▦</span><span class="entity-code">${escapeHtml(dept.code)}</span></div><h2>${escapeHtml(dept.name)}</h2><p>${escapeHtml(dept.description || "No description added.")}</p><div class="entity-meta"><span><strong>${dept.course_count}</strong> courses</span><span><strong>${dept.student_count}</strong> students</span></div><div class="entity-actions"><button class="button button-secondary button-small" data-edit="department" data-id="${dept.id}">Edit</button><button class="button button-danger button-small" data-delete="department" data-id="${dept.id}">Delete</button></div></article>`).join("") : empty("▦", "No departments yet", "Create a department before adding courses or students.");
    } catch (error) { showError("#departments-grid", error.message); }
  }

  async function loadCourses() {
    showLoading("#courses-grid");
    try {
      const [courseData, deptData, subjectData] = await Promise.all([getJson("/api/courses"), getJson("/api/departments"), getJson("/api/subjects")]);
      state.courses = courseData.courses;
      state.departments = deptData.departments;
      state.subjects = subjectData.subjects;
      $("#courses-summary").innerHTML = `<strong>${state.courses.length}</strong> course${state.courses.length === 1 ? "" : "s"} in your catalog`;
      $("#courses-grid").innerHTML = state.courses.length ? state.courses.map((course) => `<article class="entity-card"><div class="entity-card-top"><span class="entity-icon">▤</span><span class="entity-code">${escapeHtml(course.code)}</span></div><h2>${escapeHtml(course.name)}</h2><p>${escapeHtml(course.description || course.department_name)}</p><div class="entity-meta"><span>${escapeHtml(course.department_name)}</span><span><strong>${course.duration_years}</strong> years</span><span><strong>${course.student_count}</strong> students</span></div><div class="entity-actions"><button class="button button-secondary button-small" data-edit="course" data-id="${course.id}">Edit</button><button class="button button-danger button-small" data-delete="course" data-id="${course.id}">Delete</button></div></article>`).join("") : empty("▤", "No courses yet", "Add departments first, then build your course catalog.");
      renderSubjects();
    } catch (error) { showError("#courses-grid", error.message); }
  }

  function renderSubjects() {
    if (!$("#subjects-table")) return;
    $("#subjects-table").innerHTML = state.subjects.length ? `<div class="table-container"><table><thead><tr><th>Subject</th><th>Code</th><th>Course</th><th>Credits</th><th>Actions</th></tr></thead><tbody>${state.subjects.map((subject) => `<tr><td><b>${escapeHtml(subject.name)}</b></td><td class="table-id">${escapeHtml(subject.code)}</td><td>${escapeHtml(subject.course_name)}</td><td>${subject.credits}</td><td><div class="row-actions"><button class="table-action" data-edit="subject" data-id="${subject.id}" title="Edit subject" aria-label="Edit subject">✎</button><button class="table-action delete" data-delete="subject" data-id="${subject.id}" title="Delete subject" aria-label="Delete subject">×</button></div></td></tr>`).join("")}</tbody></table></div>` : empty("▤", "No subjects yet", "Add subjects to record results for students.");
  }

  async function loadAttendance() {
    showLoading("#attendance-table");
    try {
      const [attendance, students] = await Promise.all([getJson("/api/attendance"), getJson("/api/students")]);
      state.attendance = attendance.attendance;
      state.students = students.students;
      const present = state.attendance.filter((row) => row.status === "Present").length;
      const count = state.attendance.length;
      $("#attendance-summary-cards").innerHTML = [
        statCard("Records", count, "◷", "#6374df", "All recorded attendance"),
        statCard("Present", present, "✓", "#35ad89", count ? `${Math.round(present * 100 / count)}% of records` : "No records yet"),
        statCard("Absent", state.attendance.filter((row) => row.status === "Absent").length, "×", "#df6e76", "Requires follow-up"),
        statCard("Other", state.attendance.filter((row) => ["Late", "Excused"].includes(row.status)).length, "↗", "#e5a545", "Late or excused"),
      ].join("");
      renderAttendance();
    } catch (error) { showError("#attendance-table", error.message); }
  }

  function renderAttendance() {
    if (!$("#attendance-table")) return;
    const search = ($("#attendance-search")?.value || "").toLowerCase();
    const date = $("#attendance-date-filter")?.value || "";
    const status = $("#attendance-status-filter")?.value || "";
    const rows = state.attendance.filter((row) =>
      (!search || `${row.student_name} ${row.student_number}`.toLowerCase().includes(search)) &&
      (!date || row.attendance_date === date) && (!status || row.status === status)
    );
    $("#attendance-table").innerHTML = rows.length ? `<table><thead><tr><th>Student</th><th>Date</th><th>Status</th><th>Notes</th><th>Actions</th></tr></thead><tbody>${rows.map((row) => `<tr><td><div class="table-person"><span class="mini-avatar">${escapeHtml(initials(row.student_name))}</span><span><b>${escapeHtml(row.student_name)}</b><small>${escapeHtml(row.student_number)}</small></span></div></td><td>${formatDate(row.attendance_date)}</td><td>${badge(row.status)}</td><td>${escapeHtml(row.notes || "—")}</td><td><div class="row-actions"><button class="table-action" data-edit="attendance" data-id="${row.id}" title="Edit attendance" aria-label="Edit attendance">✎</button><button class="table-action delete" data-delete="attendance" data-id="${row.id}" title="Delete attendance" aria-label="Delete attendance">×</button></div></td></tr>`).join("")}</tbody></table>` : empty("◷", "No attendance records", "Record attendance or adjust your filters.");
  }

  async function loadResults() {
    showLoading("#results-table");
    try {
      const [resultData, studentData, subjectData] = await Promise.all([getJson("/api/results"), getJson("/api/students"), getJson("/api/subjects")]);
      state.results = resultData.results;
      state.students = studentData.students;
      state.subjects = subjectData.subjects;
      setOptions("#results-student-filter", state.students, "All students", "id", "full_name");
      setOptions("#results-subject-filter", state.subjects, "All subjects", "id", "name");
      renderResults();
    } catch (error) { showError("#results-table", error.message); }
  }

  function renderResults() {
    if (!$("#results-table")) return;
    const search = ($("#results-search")?.value || "").toLowerCase();
    const student = $("#results-student-filter")?.value || "";
    const subject = $("#results-subject-filter")?.value || "";
    const rows = state.results.filter((row) =>
      (!search || `${row.student_name} ${row.student_number} ${row.subject_name} ${row.subject_code}`.toLowerCase().includes(search)) &&
      (!student || String(row.student_id) === student) && (!subject || String(row.subject_id) === subject)
    );
    const average = rows.length ? (rows.reduce((sum, row) => sum + row.score * 100 / row.max_score, 0) / rows.length).toFixed(1) : "0.0";
    $("#results-summary").innerHTML = `<strong>${rows.length}</strong> result${rows.length === 1 ? "" : "s"} shown <span>·</span> ${average}% average score`;
    $("#results-table").innerHTML = rows.length ? `<table><thead><tr><th>Student</th><th>Subject</th><th>Academic year</th><th>Score</th><th>Grade</th><th>Actions</th></tr></thead><tbody>${rows.map((row) => `<tr><td><div class="table-person"><span class="mini-avatar">${escapeHtml(initials(row.student_name))}</span><span><b>${escapeHtml(row.student_name)}</b><small>${escapeHtml(row.student_number)}</small></span></div></td><td><b>${escapeHtml(row.subject_name)}</b><small class="cell-subtext">${escapeHtml(row.subject_code)}</small></td><td>${escapeHtml(row.academic_year)}</td><td>${row.score} / ${row.max_score} <small class="cell-subtext">${(row.score * 100 / row.max_score).toFixed(1)}%</small></td><td><span class="grade grade-${row.grade.toLowerCase()}">${escapeHtml(row.grade)}</span></td><td><div class="row-actions"><button class="table-action" data-edit="result" data-id="${row.id}" title="Edit result" aria-label="Edit result">✎</button><button class="table-action delete" data-delete="result" data-id="${row.id}" title="Delete result" aria-label="Delete result">×</button></div></td></tr>`).join("")}</tbody></table>` : empty("✳", "No results found", "Add an academic result or change your filters.");
  }

  function renderReports() {
    if (!state.dashboard) return;
    const { stats, attendance, admissions } = state.dashboard;
    $("#report-stats").innerHTML = [
      statCard("Total students", stats.total_students, "♙", "#6374df", "All enrolled students"),
      statCard("Departments", stats.total_departments, "▦", "#e5a545", "Academic departments"),
      statCard("Courses", stats.total_courses, "▤", "#8c78d8", "Available programs"),
      statCard("Average score", `${stats.average_score}%`, "✳", "#35ad89", `${stats.result_count} academic results`),
    ].join("");
    const total = attendance.reduce((sum, item) => sum + item.count, 0);
    $("#report-attendance").innerHTML = total ? attendance.map((item) => {
      const percent = Math.round(item.count * 100 / total);
      const color = { Present: "#39b58c", Absent: "#e47b82", Late: "#e7aa4e", Excused: "#7887df" }[item.status];
      return `<div class="attendance-line"><span>${escapeHtml(item.status)}</span><div class="progress-track"><div class="progress-fill" style="--fill:${color};width:${percent}%"></div></div><b>${percent}%</b></div>`;
    }).join("") : empty("◷", "No attendance data", "Attendance summaries appear once records are entered.");
    const max = Math.max(1, ...admissions.map((item) => item.count));
    $("#report-admissions").innerHTML = admissions.map((item) => `<div class="month-column"><b>${item.count}</b><div class="month-bar" style="height:${Math.max(3, item.count / max * 95)}px"></div><span>${escapeHtml(item.month)}</span></div>`).join("");
  }

  function modalShell(title, subtitle, content) {
    const root = $("#modal-root");
    root.innerHTML = `<div class="modal-backdrop" data-dismiss-modal><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><div><h2 id="modal-title">${escapeHtml(title)}</h2><p>${escapeHtml(subtitle)}</p></div><button type="button" class="icon-button" data-close-modal aria-label="Close dialog">×</button></header><div class="modal-body">${content}</div></section></div>`;
    root.querySelector("[data-close-modal]").addEventListener("click", closeModal);
    root.querySelector(".modal-backdrop").addEventListener("click", (event) => {
      if (event.target === event.currentTarget || event.target.closest("[data-close-modal]")) closeModal();
    });
    document.addEventListener("keydown", handleEscape, { once: true });
  }

  function handleEscape(event) {
    if (event.key === "Escape") closeModal();
  }

  function closeModal() { $("#modal-root").innerHTML = ""; }

  function field(label, name, value = "", options = {}) {
    const full = options.full ? " full" : "";
    const required = options.required ? " required" : "";
    let control;
    if (options.options) {
      control = `<select name="${name}"${required}>${options.options.map(([val, text]) => `<option value="${escapeHtml(val)}"${String(val) === String(value) ? " selected" : ""}>${escapeHtml(text)}</option>`).join("")}</select>`;
    } else if (options.textarea) {
      control = `<textarea name="${name}" placeholder="${escapeHtml(options.placeholder || "")}"${required}>${escapeHtml(value)}</textarea>`;
    } else {
      control = `<input name="${name}" type="${options.type || "text"}" value="${escapeHtml(value)}" placeholder="${escapeHtml(options.placeholder || "")}"${options.min !== undefined ? ` min="${options.min}"` : ""}${options.max !== undefined ? ` max="${options.max}"` : ""}${options.step ? ` step="${options.step}"` : ""}${required}>`;
    }
    return `<label class="form-field${full}"><span>${escapeHtml(label)}${options.required ? " *" : ""}</span>${control}</label>`;
  }

  function optionsFor(items, label, valueKey = "id", textKey = "name") {
    return [["", label], ...items.map((item) => [item[valueKey], item[textKey]])];
  }

  function findRecord(type, id) {
    const list = { student: state.students, department: state.departments, course: state.courses, subject: state.subjects, attendance: state.attendance, result: state.results }[type] || [];
    return list.find((item) => String(item.id) === String(id));
  }

  function formSpec(type, record) {
    const editing = Boolean(record);
    if (type === "student") {
      const departments = optionsFor(state.departments, "Select a department");
      const deptId = record?.department_id || state.departments[0]?.id || "";
      const courses = optionsFor(state.courses.filter((item) => String(item.department_id) === String(deptId)), "Select a course");
      return {
        title: editing ? "Edit student profile" : "Add a student",
        subtitle: "Student details and program enrollment",
        endpoint: editing ? `/api/students/${record.id}` : "/api/students",
        method: editing ? "PUT" : "POST",
        fields: [
          field("Student ID", "student_id", record?.student_id || "", { required: true }),
          field("Full name", "full_name", record?.full_name || "", { required: true }),
          field("Email address", "email", record?.email || "", { type: "email", required: true }),
          field("Phone number", "phone", record?.phone || "", { type: "tel" }),
          field("Gender", "gender", record?.gender || "Prefer not to say", { options: [["Female", "Female"], ["Male", "Male"], ["Non-binary", "Non-binary"], ["Prefer not to say", "Prefer not to say"]] }),
          field("Date of birth", "date_of_birth", record?.date_of_birth || "", { type: "date" }),
          field("Department", "department_id", deptId, { options: departments, required: true }),
          field("Course", "course_id", record?.course_id || "", { options: courses, required: true }),
          field("Year of study", "year_of_study", record?.year_of_study || 1, { type: "number", min: 1, max: 12, required: true }),
          field("Admission date", "admission_date", record?.admission_date || isoToday, { type: "date", required: true }),
          field("Status", "status", record?.status || "Active", { options: [["Active", "Active"], ["Inactive", "Inactive"], ["Graduated", "Graduated"], ["Suspended", "Suspended"]] }),
          field("Profile photo URL", "profile_photo", record?.profile_photo || "", { type: "url", full: true, placeholder: "https://example.com/photo.jpg" }),
          field("Address", "address", record?.address || "", { textarea: true, full: true }),
        ],
      };
    }
    if (type === "department") return {
      title: editing ? "Edit department" : "Add a department", subtitle: "Institutional academic organization",
      endpoint: editing ? `/api/departments/${record.id}` : "/api/departments", method: editing ? "PUT" : "POST",
      fields: [field("Department name", "name", record?.name || "", { required: true }), field("Department code", "code", record?.code || "", { required: true }), field("Description", "description", record?.description || "", { textarea: true, full: true })],
    };
    if (type === "course") return {
      title: editing ? "Edit course" : "Add a course", subtitle: "Create a program within a department",
      endpoint: editing ? `/api/courses/${record.id}` : "/api/courses", method: editing ? "PUT" : "POST",
      fields: [field("Course name", "name", record?.name || "", { required: true }), field("Course code", "code", record?.code || "", { required: true }), field("Department", "department_id", record?.department_id || "", { options: optionsFor(state.departments, "Select a department"), required: true }), field("Duration (years)", "duration_years", record?.duration_years || 4, { type: "number", min: 1, max: 12, required: true }), field("Description", "description", record?.description || "", { textarea: true, full: true })],
    };
    if (type === "subject") return {
      title: editing ? "Edit subject" : "Add a subject", subtitle: "Link a subject to a course for grading",
      endpoint: editing ? `/api/subjects/${record.id}` : "/api/subjects", method: editing ? "PUT" : "POST",
      fields: [field("Subject name", "name", record?.name || "", { required: true }), field("Subject code", "code", record?.code || "", { required: true }), field("Course", "course_id", record?.course_id || "", { options: optionsFor(state.courses, "Select a course"), required: true }), field("Credits", "credits", record?.credits || 3, { type: "number", min: 1, max: 30, required: true })],
    };
    if (type === "attendance") return {
      title: editing ? "Edit attendance" : "Record attendance", subtitle: "Record one student's attendance for a date",
      endpoint: editing ? `/api/attendance/${record.id}` : "/api/attendance", method: editing ? "PUT" : "POST",
      fields: [field("Student", "student_id", record?.student_id || "", { options: optionsFor(state.students, "Select a student", "id", "full_name"), required: true }), field("Date", "attendance_date", record?.attendance_date || isoToday, { type: "date", required: true }), field("Status", "status", record?.status || "Present", { options: [["Present", "Present"], ["Absent", "Absent"], ["Late", "Late"], ["Excused", "Excused"]] }), field("Notes", "notes", record?.notes || "", { textarea: true, full: true })],
    };
    const student = state.students.find((item) => String(item.id) === String(record?.student_id)) || state.students[0];
    const subjects = state.subjects.filter((item) => !student || String(item.course_id) === String(student.course_id));
    return {
      title: editing ? "Edit result" : "Add an academic result", subtitle: "Record a score for a student's course subject",
      endpoint: editing ? `/api/results/${record.id}` : "/api/results", method: editing ? "PUT" : "POST",
      fields: [field("Student", "student_id", record?.student_id || "", { options: optionsFor(state.students, "Select a student", "id", "full_name"), required: true }), field("Subject", "subject_id", record?.subject_id || "", { options: optionsFor(subjects, "Select a subject"), required: true }), field("Academic year", "academic_year", record?.academic_year || `${today.getFullYear()}-${today.getFullYear() + 1}`, { required: true }), field("Score", "score", record?.score ?? "", { type: "number", min: 0, step: "0.01", required: true }), field("Maximum score", "max_score", record?.max_score || 100, { type: "number", min: 0.01, step: "0.01", required: true })],
    };
  }

  function openForm(type, id = "") {
    const record = id ? findRecord(type, id) : null;
    if (id && !record) return toast("This record is no longer available. Refresh and try again.", true);
    const spec = formSpec(type, record);
    const formHtml = `<form id="record-form"><div id="form-error" class="form-error" hidden></div><div class="form-grid">${spec.fields.join("")}</div><footer class="modal-footer"><button type="button" class="button button-secondary" data-close-modal>Cancel</button><button class="button button-primary" type="submit">${record ? "Save changes" : "Create record"}</button></footer></form>`;
    modalShell(spec.title, spec.subtitle, formHtml);
    $("[data-close-modal]", $("#modal-root")).addEventListener("click", closeModal);
    const form = $("#record-form");
    form.addEventListener("change", (event) => {
      if (type === "student" && event.target.name === "department_id") {
        const courses = state.courses.filter((course) => String(course.department_id) === event.target.value);
        const control = form.elements.course_id;
        control.innerHTML = optionsFor(courses, "Select a course").map(([value, text]) => `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`).join("");
      }
      if (type === "result" && event.target.name === "student_id") {
        const selected = state.students.find((student) => String(student.id) === event.target.value);
        const subjects = state.subjects.filter((subject) => selected && String(subject.course_id) === String(selected.course_id));
        form.elements.subject_id.innerHTML = optionsFor(subjects, "Select a subject").map(([value, text]) => `<option value="${escapeHtml(value)}">${escapeHtml(text)}</option>`).join("");
      }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      submit.innerHTML = '<span class="spinner"></span>Saving…';
      const values = Object.fromEntries(new FormData(form));
      for (const key of ["department_id", "course_id", "year_of_study", "duration_years", "credits"]) {
        if (values[key] !== undefined && values[key] !== "") values[key] = Number(values[key]);
      }
      if (type === "attendance" || type === "result") {
        values.student_id = Number(values.student_id);
      }
      if (type === "result") {
        values.subject_id = Number(values.subject_id);
        values.score = Number(values.score);
        values.max_score = Number(values.max_score);
      }
      try {
        await sendJson(spec.endpoint, spec.method, values);
        closeModal();
        toast(record ? "Changes saved successfully." : "Record created successfully.");
        await reloadPageData();
      } catch (error) {
        const errorBox = $("#form-error");
        errorBox.textContent = error.message;
        errorBox.hidden = false;
        submit.disabled = false;
        submit.textContent = record ? "Save changes" : "Create record";
      }
    });
  }

  async function deleteRecord(type, id) {
    const labels = { student: "student", department: "department", course: "course", subject: "subject", attendance: "attendance record", result: "result" };
    if (!window.confirm(`Delete this ${labels[type] || "record"}? This action cannot be undone.`)) return;
    const endpoints = { student: "students", department: "departments", course: "courses", subject: "subjects", attendance: "attendance", result: "results" };
    try {
      const response = await api(`/api/${endpoints[type]}/${id}`, { method: "DELETE" });
      const body = await response.json();
      toast(body.message || "Record deleted.");
      await reloadPageData();
    } catch (error) { toast(error.message, true); }
  }

  async function viewStudent(id) {
    try {
      const { student } = await getJson(`/api/students/${id}`);
      const photo = student.profile_photo
        ? `<img class="profile-photo" src="${escapeHtml(student.profile_photo)}" alt="">`
        : `<span class="profile-photo profile-fallback">${escapeHtml(initials(student.full_name))}</span>`;
      const profile = `<div class="profile-head">${photo}<div><h3>${escapeHtml(student.full_name)}</h3><p>${escapeHtml(student.student_id)} · ${badge(student.status)}</p></div></div><div class="profile-grid">${[
        ["Email", student.email], ["Phone", student.phone || "—"], ["Gender", student.gender],
        ["Date of birth", formatDate(student.date_of_birth)], ["Department", student.department_name],
        ["Course", student.course_name], ["Year of study", `Year ${student.year_of_study}`],
        ["Admission date", formatDate(student.admission_date)], ["Address", student.address || "—"],
        ["Attendance records", student.attendance.length], ["Result records", student.results.length],
      ].map(([label, value]) => `<div class="profile-item"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join("")}</div><footer class="modal-footer"><button type="button" class="button button-secondary" data-close-modal>Close</button><button type="button" class="button button-primary" data-edit="student" data-id="${student.id}">Edit profile</button></footer>`;
      modalShell("Student profile", "Personal information and academic enrollment", profile);
      $("[data-close-modal]", $("#modal-root")).addEventListener("click", closeModal);
    } catch (error) { toast(error.message, true); }
  }

  async function downloadCsv() {
    try {
      const response = await api("/api/reports/students.csv");
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "student-report.csv";
      link.click();
      URL.revokeObjectURL(link.href);
      toast("Student report downloaded.");
    } catch (error) { toast(error.message, true); }
  }

  async function reloadPageData() {
    if (page === "dashboard") await loadDashboard();
    if (page === "students") await loadStudents();
    if (page === "departments") await loadDepartments();
    if (page === "courses") await loadCourses();
    if (page === "attendance") await loadAttendance();
    if (page === "results") await loadResults();
    if (page === "reports") await loadDashboard();
  }

  async function initialize() {
    setUser(JSON.parse(localStorage.getItem("campuscore_user") || "null"));
    navEvents();
    actionEvents();
    bindFilters();
    window.addEventListener("resize", () => {
      if (state.dashboard) drawAdmissions(state.dashboard.admissions);
    });
    try {
      const { user } = await getJson("/api/auth/me");
      localStorage.setItem("campuscore_user", JSON.stringify(user));
      setUser(user);
    } catch (error) { console.error(error); }
    await reloadPageData();
  }

  initialize();
})();

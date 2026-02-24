# SmartID Ecosystem — Comprehensive Project Report

**Document Version:** 1.0  
**Last Updated:** February 2026  
**Project:** SmartID Ecosystem (COMSATS University Islamabad, Sahiwal Campus — FYP)

---

## 1. Executive Summary

The **SmartID Ecosystem** is an integrated digital identity and attendance platform for educational institutions. It provides:

- **Unified login** (single entry point; role-based redirect after authentication)
- **Admin-controlled user enrollment** with digital consent, optional course linking, and multi-method auth setup (Face, Fingerprint, RFID)
- **Real-time attendance** with On time / Late status (e.g. 20-minute window from session start)
- **Role-specific portals** for Students, Professors, Parents, and Administrators
- **Session management** (start/end by staff/teachers, optional course and location)
- **Reporting and analytics** (daily/weekly/monthly reports, course rosters, CSV export, status filters)
- **Automated alert rules** (location-based or **course-based** thresholds with notifications to admins)
- **IoT readiness** (REST API for Raspberry Pi: RFID scan → face match → mark attendance; offline batch sync)
- **Privacy and compliance** (consent records, encrypted biometric/RFID storage, privacy compliance view for admins)
- **System health** (device registry, API keys, global toggles for Face/Fingerprint/RFID)

The system is built with **Django 4.2+**, **Python 3.9+**, and a responsive **HTML5/CSS3/JavaScript (Bootstrap 5)** front end, aligned with the SRS and Scope documents.

---

## 2. Alignment with SRS & Scope

| SRS / Scope Item | Implementation Status |
|------------------|------------------------|
| **FR-1** User registration with institutional ID and auth method choice | ✅ Admin enrollment in dashboard; wizard (steps: basic info → consent → method-specific); Face/Fingerprint/RFID options |
| **FR-2** Data capture & consent (digital consent form) | ✅ ConsentRecord; consent checkboxes in enrollment; admin-only enrollment |
| **FR-3** Identity verification (face/fingerprint/RFID) | ✅ RFID terminal + web login; Face/Fingerprint ready (device API + enrollment placeholders) |
| **FR-4** Liveness detection | ⏳ Placeholder; to be implemented with face hardware |
| **FR-5** Automatic attendance recording | ✅ On successful auth (terminal/API); unique per user per session; On time/Late status |
| **FR-6** Attendance report generation | ✅ Daily/weekly/monthly reports; by user/location; CSV export; status column and filters |
| **FR-7** Smart door unlock (IoT) | ✅ Device API for Pi; door/signal can be triggered from same backend |
| **FR-8** Access logging | ✅ AccessLog model; logging on terminal/API access |
| **FR-9** Attendance alerts to students | ✅ Notifications app; missed class / failed auth types |
| **FR-10** System notifications to admins | ✅ notify_admins; access_alert; alert rules trigger admin notifications |
| **FR-11** Data encryption (AES-256–style) | ✅ Biometric/RFID encryption via cryptography (Fernet/PBKDF2); BIOMETRIC_ENCRYPTION_KEY |
| **FR-12** Data retention and deletion control | ✅ Consent and data retention ack; structure for deletion on withdrawal |
| **FR-13** Access control for sensitive data | ✅ Role-based access; admin-only views; audit via AccessLog |
| **OE-1 to OE-5** Operating environment | ✅ Web-based; Django; browser and OS support as specified |
| **CO-1 to CO-6** Design constraints | ✅ Django, SQLite/MySQL, HTML5/CSS3/JS, Bootstrap; open-source stack |

---

## 3. Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Django 4.2+, Python 3.9+ |
| **Database** | SQLite (development); MySQL-compatible for production (OE-4, CO-2) |
| **Frontend** | HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons |
| **API** | Django REST Framework, token auth; device auth via X-Device-Id / X-Device-Key |
| **Security** | Django auth, CSRF, role-based decorators; cryptography for biometric/RFID |
| **Notifications** | In-app (Notification model); email can be wired via Django email backend |

---

## 4. Application Structure

| App | Purpose |
|-----|---------|
| **users** | Custom User (email, institutional_id, role), consent, auth method preference, RFID credentials, parent–student links; login, profile, password reset |
| **attendance** | Locations, Courses, CourseEnrollment, AttendanceSession, AttendanceRecord (with status), AccessLog, PendingRFIDScan, LeaveRequest; terminal login; student/teacher/parent portals; session management; course management |
| **dashboard** | Role-based home; reports; analytics; manage users (CRUD, RFID enroll); locations; system health (devices, auth toggles); privacy compliance; alert rules (create/toggle/delete/check) |
| **notifications** | Notification model; list view; context processor for unread count; notify() / notify_admins() |
| **api** | REST ViewSets (locations, sessions, records, courses); device endpoints (active-session, rfid-scan, face-match, offline-batch); mark-attendance; student-stats; health check |

---

## 5. User Roles and Portals

| Role | Login | Post-login | Main Capabilities |
|------|--------|------------|-------------------|
| **Student** | Same login page (email + password or institutional ID) | Student dashboard | View attendance history (with status filter), stats per course, timetable, leave requests; use terminal (RFID) to mark attendance |
| **Professor** | Same login page | Teacher dashboard | View courses; start/end sessions (for their courses); class attendance; roster (with On time/Late counts); export CSV; send notifications; schedule; analytics; leave review |
| **Parent** | Same login page | Parent dashboard | View linked students; each child’s attendance (with status), stats, timetable, leaves (read-only) |
| **Administrator** | Same login page | Admin dashboard | All of the above; manage users (create/edit/toggle/reset password, enroll RFID, parent links); manage locations; manage courses and enrollments; reports (with status filter); analytics; system health (devices, auth toggles); privacy compliance; alert rules (location- and course-based); Django admin access |

Single login URL; redirect by role after authentication.

---

## 6. Core Features Implemented

### 6.1 User Enrollment (Module 1 — FR-1, FR-2)

- **Access:** Admin only (dashboard → Manage Users → Create User / Enroll).
- **Flow:** Multi-step wizard: (1) Basic info (email, institutional_id, first name, last name, role, phone, password), (2) Consent & auth method (Face/Fingerprint/RFID, consent checkboxes), (3) Method-specific (RFID tag input, Face placeholder/camera, Fingerprint “Skip — add later”).
- **Validation:** Unique institutional_id; format guidance (e.g. XX00-XXX-000) for students.
- **Post-enrollment:** RFID enrollment page if method is RFID and tag not yet set; optional face/fingerprint later from profile or future flows.

### 6.2 Authentication (Module 2 — FR-3)

- **Web login:** Email (or institutional ID where supported) + password; single page; “Forgot password” and “Contact admin to be enrolled.”
- **Terminal (RFID):** Dedicated terminal page; scan/lookup by RFID or institutional ID; marks attendance for active session at selected location.
- **Device API (Pi):** RFID scan → pending queue; face match (embedding) → match to pending, then create AttendanceRecord (on_time/late); offline batch of events for sync when back online.

### 6.3 Real-Time Attendance (Module 3 — FR-5)

- **Recording:** One record per user per session; timestamp and location; **status** = On time (within configurable window, e.g. 20 min from session start) or Late.
- **Places recorded:** Web terminal, device API (face match after RFID).
- **Display:** Student history, teacher roster/export, reports, parent child attendance, dashboard recent list; **Status** column and filters (e.g. All / On time / Late) where applicable.

### 6.4 Session Management

- **Start session:** Staff/Professor; required **Location**, optional **Course**; prevents duplicate active session per location.
- **End session:** Button per active session.
- **Visibility:** Professors see only sessions they created or linked to their courses; admins see all.
- **UI:** Active and recently ended sessions tables; course shown when linked.

### 6.5 Courses and Enrollments

- **Courses:** Code, name, professor, location, schedule (day, start/end time); admin/professor management.
- **Enrollment:** Admin (and authorized roles) enroll students in courses; used for roster, stats, session linking, and course-based alert rules.

### 6.6 Reports and Export (FR-6)

- **Dashboard reports:** Daily / weekly / monthly; by user and by location; **Status** filter (All / On time / Late); CSV export includes Status column.
- **Teacher export:** Per-course CSV (Student ID, Name, Email, Date/Time, Location, Session, **Status**).
- **Student history:** Filters by course, location, date range, **status**; pagination.

### 6.7 Analytics

- **Admin analytics:** High-level metrics; charts (e.g. 7-day trend, per-course); links to detailed views.
- **Teacher analytics:** Per-course stats; daily trend; links to class attendance.

### 6.8 Automated Alert Rules (Module 5 & 8 — FR-9, FR-10)

- **Configuration:** Admin → Alert Rules; create rule with **name**, **threshold %**, **time window** (daily/weekly/monthly), and either **Location** or **Course** (or both; course takes precedence for evaluation).
- **Course-based:** Attendance % = (actual marks in window for that course) / (enrolled × sessions in window); alert when below threshold.
- **Location-based:** Same as before (distinct users attended at location vs total students).
- **Actions:** Enable/Pause, Delete, “Check All Rules Now”; notifications sent to admins.
- **Automation:** Management command `python manage.py check_alerts` for cron/Task Scheduler.

### 6.9 Notifications (Module 6 — UC-5)

- **Types:** missed_class, failed_auth, access_alert, system.
- **In-app:** Notification list; unread count in UI (e.g. sidebar).
- **Recipients:** Students, admins (e.g. access_alert, system); teachers can send to course students.

### 6.10 IoT / Device API (Module 4 — FR-7, FR-8)

- **Endpoints:**  
  - `GET /api/device/active-session/` — active session for device’s location (course, on_time_until).  
  - `POST /api/device/rfid-scan/` — add user to pending queue for session.  
  - `POST /api/device/face-match/` — match embedding to pending queue; create AttendanceRecord (on_time/late); return record + status.  
  - `POST /api/device/offline-batch/` — process queued events when back online.
- **Auth:** X-Device-Id and X-Device-Key (stored in SystemDevice; API key generated on register).
- **Flow:** RFID first → then face match within TTL; optional door/signal integration on same backend.

### 6.11 System Health and Settings (Module 9)

- **Device registry:** Register IoT devices (Raspberry Pi, sensor types); view ID and API Key for Pi requests.
- **Auth toggles:** Global enable/disable for Face, Fingerprint, RFID (SystemSetting singleton).
- **UI:** System Health page under dashboard; register device modal; toggle buttons.

### 6.12 Privacy and Compliance

- **Consent:** Stored in ConsentRecord (biometric, RFID, data retention ack).
- **Privacy compliance view:** Admin list of users with consent status; flag users who have not signed digital consent (FR-2, oversight plane).
- **Encryption:** Biometric/RFID data encrypted (Fernet/PBKDF2) before storage (FR-11).

### 6.13 Leave Requests

- **Student:** Submit leave request (course, date, reason).
- **Teacher:** Review (approve/reject) for their courses.
- **Parent:** View child’s leaves (read-only).

### 6.14 Profile and ID Card

- **Profile:** Edit first name, last name, phone; consistent form styling; optional future face/fingerprint from profile.
- **ID card:** View/print campus ID (registration number, name, etc.).

---

## 7. Database Models (Summary)

| App | Model | Purpose |
|-----|--------|---------|
| **users** | User | Email, institutional_id, role, phone; custom auth |
| **users** | ConsentRecord | Biometric/RFID/data retention consent |
| **users** | UserAuthMethod | Preferred auth method per user |
| **users** | RFIDCredential | RFID tag per user (encrypted) |
| **users** | ParentStudentLink | Parent ↔ student linking |
| **attendance** | Location | Venues (classroom, lab, gate, etc.) |
| **attendance** | Course | Course metadata, professor, location, schedule |
| **attendance** | CourseEnrollment | Student–course enrollment |
| **attendance** | AttendanceSession | Session (location, optional course, started/ended) |
| **attendance** | AttendanceRecord | One per user per session; status on_time/late |
| **attendance** | AccessLog | Access events (FR-8) |
| **attendance** | PendingRFIDScan | Queue for RFID → face match (Pi flow) |
| **attendance** | LeaveRequest | Student leave; status; reviewer |
| **dashboard** | SystemDevice | IoT device registry; API key; status |
| **dashboard** | SystemSetting | Global Face/Fingerprint/RFID toggles; session timeout; max failed attempts |
| **dashboard** | AlertRule | Threshold rules; location and/or course; time window |
| **notifications** | Notification | In-app notifications; type; read flag |

---

## 8. API Endpoints (Summary)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health/` | Health check |
| POST | `/api/auth/token/` | Obtain auth token |
| GET/POST | `/api/locations/`, `/api/sessions/`, `/api/records/`, `/api/courses/` | REST CRUD (ViewSets) |
| POST | `/api/mark-attendance/` | Mark attendance (authenticated user) |
| GET | `/api/device/active-session/` | Pi: get active session for device location |
| POST | `/api/device/rfid-scan/` | Pi: add RFID scan to pending queue |
| POST | `/api/device/face-match/` | Pi: match face embedding; create record (on_time/late) |
| POST | `/api/device/offline-batch/` | Pi: submit offline event batch |
| GET | `/api/student-stats/` | Current user’s stats |
| GET | `/api/student-stats/<id>/` | Stats for given user (authorized) |

---

## 9. UI and Design

- **Base template:** Sidebar navigation (role-based links), top bar, main content; SmartID branding.
- **Design tokens:** CSS variables for primary, backgrounds, text hierarchy, semantic colors (success, warning, danger, info); used across cards, buttons, badges, forms.
- **Responsiveness:** Bootstrap 5 grid; layouts adapt to screen size; touch-friendly where applicable.
- **Templates (49):** Login, profile, password reset; dashboard homes (student, teacher, parent, staff); attendance (history, stats, timetable, leaves); teacher (dashboard, class attendance, roster, export, notify, schedule, analytics, leaves); parent (dashboard, child attendance/stats/timetable/leaves); admin (manage users, create/edit user, enroll RFID, parent links, locations, reports, analytics, system health, privacy compliance, alert rules); terminal login/success; notifications list; ID card; course management and enrollment.

---

## 10. Sprints Implemented (Summary)

### Sprint A (UI and behaviour)

- **Start session:** Optional **Course** dropdown; course shown in active/recent sessions tables.
- **On time / Late:** Status shown in student history, teacher roster (On time/Late counts), teacher CSV export, dashboard reports (table + CSV), parent child attendance, student home recent list; Status filter on student history and dashboard reports.
- **Fingerprint panel:** Message and “Skip — add later” button in enrollment wizard.

### Sprint B (Filters and admin)

- **Student history:** Status filter (All / On time / Late); pagination preserves filters.
- **Dashboard reports:** Status filter; CSV export respects filter.
- **Admin:** AttendanceRecord list shows status; list_filter by status and location.

### Sprint C (Intelligence plane and robustness)

- **Course-based alert rules:** AlertRule has optional **course** FK; optional **location**; admin can create rules by course (class) or location; evaluation logic for course (% = actual marks / (enrolled × sessions in window)); template updated with Course dropdown and column.
- **Sessions query:** manage_sessions uses filtered queryset then single slice (`list(recent_sessions_qs[:20])`) to avoid “Cannot filter a query once a slice has been taken.”
- **check_alerts command:** Updated to support both course-based and location-based rules.

---

## 11. Security and Access Control

- **Authentication:** Django session; login required for all role portals; single login page.
- **Authorization:** Decorators: `@role_required(Role.STUDENT)`, `@role_required(Role.PROFESSOR, Role.ADMIN)`, `@staff_required`, `@admin_required`; professor-scoped data (own courses/sessions); parent-scoped (linked students only).
- **Device API:** Custom device auth (X-Device-Id, X-Device-Key) validated against SystemDevice.
- **CSRF:** Enabled on forms and POST requests.
- **Sensitive data:** Biometric/RFID encrypted; consent and access control as per FR-11, FR-12, FR-13.

---

## 12. Testing

- **Unit/integration tests:** Present in `users`, `attendance`, `dashboard`, `notifications`, `api` (e.g. login, enrollment, session start/end, student history, teacher roster, reports, alert rules, device API, access control).
- **Run:** `python manage.py test` (or per-app).

---

## 13. Deployment and Setup

- **Migrations:** `python manage.py migrate` (run after pull or DB change).
- **Superuser:** `python manage.py createsuperuser`; set institutional_id and role in admin if needed.
- **Locations:** Create at least one location (e.g. via Django admin or dashboard Manage Locations) for attendance and sessions.
- **Optional:** SECRET_KEY, DEBUG, ALLOWED_HOSTS, BIOMETRIC_ENCRYPTION_KEY; production DB (e.g. MySQL) as per OE-4.

---

## 14. Outstanding / Future Work

- **Face recognition:** End-to-end face enrollment (capture → embedding → store) and Pi-side embedding extraction; liveness (FR-4) when hardware is chosen.
- **Fingerprint:** Hardware integration and enrollment when sensor available.
- **Performance:** Ensure analytics and report queries meet SRS response-time targets (e.g. &lt; 3 s) under load; indexing and query tuning as needed.
- **Cron / Task Scheduler:** Schedule `check_alerts` (e.g. daily) and `auto_end_sessions` (e.g. every 5–15 min) — see **docs/SCHEDULED_TASKS.md** for Windows and Linux instructions.
- **Email notifications:** Configure Django email via env (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`); set `NOTIFICATIONS_SEND_EMAIL=true` to also send in-app notifications by email to recipients (FR-9, FR-10). Default remains console backend for development.

---

## 15. Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial comprehensive report (all modules, sprints A–C, API, DB, security, UI). |

---

*This report reflects the state of the SmartID Ecosystem codebase as of the last update. For SRS and Scope references, see the project’s requirement and scope documents.*

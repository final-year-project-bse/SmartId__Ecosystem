# SmartID Ecosystem

**Enhanced SmartID Ecosystem** – intelligent, inclusive authentication and access control for university campuses (COMSATS FYP, Scope & SRS compliant).

## Features (from Scope & SRS)

- **Module 1 – User Enrollment:** Web registration with institutional ID, choice of auth method (Face, Fingerprint, RFID), and digital consent (FR-1, FR-2).
- **Module 2 – Multi-Modal Authentication:** RFID-based terminal login and web login; face/fingerprint ready for hardware integration (FR-3, FR-4).
- **Module 3 – Real-Time Attendance:** Automatic recording on successful auth; unique per user per session (FR-5).
- **Module 4 – IoT Access Control:** Terminal flow for RFID; Raspberry Pi / smart lock integration can send requests to the same backend (FR-7).
- **Module 5 – Admin Dashboard & Reporting:** Daily/weekly/monthly reports, by user and by location (FR-6).
- **Module 6 – Notifications:** In-app notifications; email can be wired via Django email backend (FR-9, FR-10).
- **Module 7 – Privacy & Consent:** Encrypted biometric/RFID storage (AES-256–style), consent records (FR-11, FR-12, FR-13).
- **Module 8 – Predictive Analytics:** Placeholder metrics on analytics page; can be extended with ML (attendance trends, anomaly detection).
- **Module 9 – System Settings:** Admin via Django admin; optional system settings view.

## Tech Stack (SRS)

- **Backend:** Django 4.2+ (Python 3.9+)
- **Database:** SQLite (dev); MySQL compatible for production (OE-4, CO-2).
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5 (CO-3).

## Setup

1. **Clone** the repository (or copy the project to your chosen directory).

2. **Create and activate virtual environment:**
   ```bash
   cd SmartID-Ecosystem
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```
   If you see an error about `InconsistentMigrationHistory` (e.g. admin applied before users), delete `db.sqlite3` and run `migrate` again.

5. **Create superuser (admin):**
   ```bash
   python manage.py createsuperuser
   ```
   Use email as username. Then in Django Admin set **institutional_id** and **role** (e.g. admin).

6. **Create locations (for attendance):**  
   Log in to `/admin/`, go to **Attendance → Locations**, add e.g. "Main Gate (GATE-01)", "Lab 1 (LAB-01)".

7. **Run server:**
   ```bash
   python manage.py runserver
   ```
   Open http://127.0.0.1:8000/

## Main URLs

| URL | Description |
|-----|-------------|
| `/` | Home (login/enroll links) |
| `/login/` | Web login (email + password) |
| `/enroll/` | User enrollment (UC-1) |
| `/attendance/terminal/` | RFID terminal login & attendance |
| `/dashboard/` | Role-based dashboard (student / professor / admin) |
| `/dashboard/reports/` | Attendance reports (daily/weekly/monthly) |
| `/dashboard/analytics/` | Admin analytics (UC-7) |
| `/dashboard/manage-users/` | Admin user list |
| `/notifications/` | User notifications (UC-5) |
| `/admin/` | Django admin (users, locations, sessions, logs) |

## Roles

- **Student:** Dashboard with own attendance; can use Terminal (RFID) to mark attendance.
- **Professor:** Dashboard + Reports (view attendance by user/location).
- **Admin:** All of the above + Analytics, Manage Users, Django Admin.

## Optional Environment Variables

- `SECRET_KEY` – Django secret (default: dev key).
- `DEBUG` – Set to `False` in production.
- `ALLOWED_HOSTS` – Comma-separated hosts.
- `BIOMETRIC_ENCRYPTION_KEY` – 32-byte key for encrypting biometric/RFID data (defaults to derived from SECRET_KEY).

## Project Source

Built from **Scope Document** and **SRS Document** (SmartID Ecosystem, COMSATS University Islamabad, Sahiwal Campus).

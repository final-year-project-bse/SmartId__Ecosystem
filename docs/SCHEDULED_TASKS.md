# Scheduled Tasks — SmartID Ecosystem

This document describes how to schedule the management commands used for alerts and timetable automation (FR-10, ghost sessions, auto-end).

---

## Commands to Schedule

| Command | Purpose | Suggested frequency |
|--------|---------|---------------------|
| `python manage.py check_alerts` | Evaluate alert rules (location/course thresholds) and notify admins when attendance % is below threshold | **Daily** (e.g. after classes end) |
| `python manage.py auto_end_sessions` | End sessions past slot `end_time`; detect ghost sessions and notify admins | **Every 5–15 minutes** during class hours |

---

## Windows (Task Scheduler)

### Prerequisites

- Use the same Python environment as the project (e.g. `venv`).
- From project root: `E:\SmartID-Ecosystem` (adjust if your path differs).

### 1. Alert check (daily)

1. Open **Task Scheduler** → **Create Basic Task**.
2. **Name:** `SmartID check_alerts`
3. **Trigger:** Daily at a fixed time (e.g. 18:00).
4. **Action:** Start a program.
   - **Program:** `E:\SmartID-Ecosystem\venv\Scripts\python.exe`
   - **Arguments:** `manage.py check_alerts`
   - **Start in:** `E:\SmartID-Ecosystem`
5. Finish and optionally set "Run whether user is logged on or not" / "Run with highest privileges" if needed.

### 2. Auto-end sessions (every 10 minutes)

1. **Create Basic Task** → Name: `SmartID auto_end_sessions`
2. **Trigger:** Daily, repeat every **10 minutes** for a duration of **1 day** (or set multiple triggers 8:00–18:00).
   - Alternatively create one task and set **Repeat task every:** 10 minutes.
3. **Action:** Start a program.
   - **Program:** `E:\SmartID-Ecosystem\venv\Scripts\python.exe`
   - **Arguments:** `manage.py auto_end_sessions`
   - **Start in:** `E:\SmartID-Ecosystem`

### PowerShell one-liners (run from project root)

```powershell
# Run once (e.g. for testing)
.\venv\Scripts\python.exe manage.py check_alerts
.\venv\Scripts\python.exe manage.py auto_end_sessions
```

---

## Linux / macOS (cron)

From project root (e.g. `/var/www/smartid` or `~/SmartID-Ecosystem`).

### Crontab entries

```cron
# Alert rules check — daily at 6 PM
0 18 * * * cd /path/to/SmartID-Ecosystem && /path/to/venv/bin/python manage.py check_alerts

# Auto-end sessions and ghost detection — every 10 minutes during 8 AM–6 PM (optional: restrict to weekdays)
*/10 8-18 * * 1-5 cd /path/to/SmartID-Ecosystem && /path/to/venv/bin/python manage.py auto_end_sessions
```

Replace `/path/to/SmartID-Ecosystem` and `/path/to/venv` with your actual paths.

### Edit crontab

```bash
crontab -e
```

Paste the lines above, save, and exit.

---

## Verification

- Run manually from project root:
  - `python manage.py check_alerts` — should print "Checked N rules…" and create admin notifications if any rule fires.
  - `python manage.py auto_end_sessions` — should end overdue sessions and create notifications for ghost slots (if any).
- After scheduling, check Task Scheduler "Last Run Result" or cron logs to confirm they run without errors.

---

## Related

- Alert rules: Dashboard → Alert Rules; create and enable rules for location or course thresholds.
- Timetable slots: Create `TimetableSlot` entries (Admin or Master Timetable) so auto-end and ghost detection work.
- Notifications: In-app in SmartID; optional email when Django email and `NOTIFICATIONS_SEND_EMAIL` are configured (see PROJECT_REPORT.md §14).

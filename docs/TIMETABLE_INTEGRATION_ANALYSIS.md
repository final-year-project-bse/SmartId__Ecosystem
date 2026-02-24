# Timetable Integration Guide — Implementation Analysis

This document compares the **Blueprinted Integration Guide** (Timetable for SmartID / CUI Sahiwal) with the **current codebase** and states what is implemented vs. not implemented.

---

## Phase 1: Database Architecture (Rule-Based / Weekly Recurrence Model)

| Guide requirement | Current state | Status |
|-------------------|---------------|--------|
| **TimetableSlot** model: course, professor, location, day_of_week, start_time, end_time | **Not present.** Schedule is on **Course** only: one `day_of_week` (char: monday–saturday), one `start_time`, one `end_time` per course. | ❌ Not implemented |
| `unique_together = ('location', 'day_of_week', 'start_time')` to prevent double-booking a room | No such constraint. Course has no uniqueness on (location, day, time). | ❌ Not implemented |
| Link to Course, Location, User (Professor) | Course already has professor and location. No separate slot table. | ⚠️ Different shape |
| **App:** guide says `courses.Course` | Project has **attendance.Course** (no separate `courses` app). | ⚠️ Naming |

**Summary:** The project uses a **one-slot-per-course** design (schedule fields on Course). The guide expects a **TimetableSlot** model that allows **multiple slots per course per week** (e.g. same course Monday 9–10 and Wednesday 2–3) and **room-level uniqueness**. That is **not** implemented.

---

## Phase 2: Workload Control (Auto-Population on Start Session)

| Guide requirement | Current state | Status |
|-------------------|---------------|--------|
| On "Start Session" load: detect current `day_of_week` and `current_time` | Not done. | ❌ Not implemented |
| Query TimetableSlot for professor’s class at this time/location | N/A (no TimetableSlot). Could be done with Course (current day + time range). | ❌ Not implemented |
| Pre-select **Course** and **Location** in the form | Form has dropdowns only; no pre-fill. | ❌ Not implemented |
| Professor only clicks "Start" | Professor must choose location and (optional) course. | ❌ Not implemented |

**Summary:** No auto-population or “one-click start” based on timetable. **Not implemented.**

---

## Phase 3: Efficiency Logic (Attendance + Auto-Close)

| Guide requirement | Current state | Status |
|-------------------|---------------|--------|
| Use **TimetableSlot.start_time + 20 min** for Late threshold | Late is based on **session.started_at + 20 min** (`ON_TIME_WINDOW_MINUTES` in device API), not timetable slot. | ⚠️ Partially aligned (same 20 min; different reference) |
| Management command: find active `AttendanceSession`, if current time > **TimetableSlot.end_time** then auto-end | No such command. Sessions are ended only via "End" button. | ❌ Not implemented |

**Summary:** On-time/late uses **session** start; there is **no** timetable-based late window and **no** auto-close command. **Not implemented** as specified.

---

## Phase 4: Intelligence Plane (Ghost Sessions)

| Guide requirement | Current state | Status |
|-------------------|---------------|--------|
| **Ghost session:** timetable slot exists but no `AttendanceSession` started | Not detected anywhere. | ❌ Not implemented |
| Generate system notification to Admin for missing instructional hours | Alert rules exist for **low attendance %** (location/course). No “ghost session” alert. | ❌ Not implemented |

**Summary:** Ghost-session detection and notifications are **not implemented**.

---

## Phase 5: Stakeholder Dashboards

| Guide requirement | Current state | Status |
|-------------------|---------------|--------|
| **Student / Parent:** read-only **grid** showing weekly schedule | Student and parent have **timetable views** (list/cards by day from enrolled courses). Not a time-slot **grid** (e.g. rows = time, columns = days). | ⚠️ Implemented as list/cards, not grid |
| **Admin:** "Master View" with filter by **Location** (room utilization) | No admin master timetable and no room-utilization view. | ❌ Not implemented |
| **Mobile-first** CSS for timetable grid | Current timetable is responsive cards; no grid layout. | ⚠️ Depends on Phase 5 layout choice |

**Summary:** Student/Parent have **a** timetable (course-based, by day); the guide’s **grid** and **admin room-utilization** view are **not** implemented.

---

## Overall Summary

| Phase | Implemented? | Notes |
|-------|--------------|------|
| **1** Database (TimetableSlot, unique_together) | ❌ No | Schedule is on Course only; one slot per course. |
| **2** Pre-fill Start Session (one-click for professor) | ❌ No | No timetable-based pre-selection. |
| **3** Timetable-based late window + auto-end command | ❌ No | Late uses session start; no auto-end. |
| **4** Ghost-session alerts | ❌ No | Not in check_alerts or elsewhere. |
| **5** Student/Parent grid + Admin room utilization | ⚠️ Partial | Student/Parent have timetable (not grid); no admin master/room view. |

---

## Clarifying Questions for Product Owner

Before implementing the guide, the following need to be decided:

### 1. **One slot vs multiple slots per course**

- **Current:** One schedule per course (one day, one start, one end).
- **Guide:** TimetableSlot allows multiple rows per course (e.g. CS101 Mon 9–10 and Wed 2–3).
- **Question:** Does CUI Sahiwal need **multiple meetings per week per course** (e.g. 2–3 lectures)? If yes, we need **TimetableSlot** (or equivalent). If one meeting per course is enough, we can keep Course-only and still add pre-fill and ghost-session logic using Course schedule.

### 2. **Where TimetableSlot lives (if added)**

- Guide references `courses.Course`; the project has **attendance.Course** and no `courses` app.
- **Question:** Should **TimetableSlot** live in the **attendance** app (and reference `attendance.Course`), or do you want a separate **courses** app and move Course there first?

### 3. **Auto-end session and timetable linkage**

- Auto-end requires knowing which **slot** (and thus which `end_time`) an active session belongs to. Right now a session has location + optional course but no direct link to a “slot.”
- **Question:** When we auto-end, should we match an active session to a slot by **(location, course, day_of_week)** and then use that slot’s `end_time`? Or should we add an explicit **TimetableSlot** FK on **AttendanceSession** when we introduce TimetableSlot?

### 4. **Late threshold: session start vs timetable start**

- Today: late = after **session.started_at + 20 min** (when the professor actually started).
- Guide: late = after **TimetableSlot.start_time + 20 min** (scheduled start).
- **Question:** Should “on time” be based on **scheduled** start (timetable) or **actual** start (session)? Scheduled is stricter (e.g. class at 9:00, professor starts at 9:10 → all marked late if we use timetable).

### 5. **Ghost session: definition and scope**

- Guide: “Timetable slot exists but no AttendanceSession was started.”
- **Question:** Should we consider a session “started” only if it is **linked to that slot** (e.g. session has slot FK or same course+location+day)? And should ghost checks run only for **today’s** slots, or also for past days (e.g. “yesterday’s slot had no session”)?

### 6. **Admin master view and room utilization**

- **Question:** For “Master View” by Location, do you want:
  - **A)** A weekly timetable **grid** (e.g. rows = time slots, columns = days) **per location**, showing which course/professor is in that room?
  - **B)** A list of slots grouped by location with filters?
  - **C)** Something else (e.g. export, report)?

### 7. **Student/Parent timetable: keep list or add grid**

- **Question:** Should Student and Parent keep the **current** list/card-by-day layout, or do you want a **time-grid** (e.g. 8–5 in 1-hour rows, days as columns) for consistency with the guide and mobile-first?

---

Once these are answered, implementation can proceed in line with the guide and CUI Sahiwal’s institutional needs without conflicting with the existing Sprint A–C behaviour.

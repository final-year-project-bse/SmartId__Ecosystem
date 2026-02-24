# Remaining UI & Backend — Analysis and Questions

Analysis of what is implemented vs what is still needed for the face + RFID attendance flow and related UI/backend.

---

## ✅ Already implemented (backend)

- Device auth (X-Device-Id, X-Device-Key), pending RFID queue, face match (cosine similarity), on_time/late (20 min), offline batch, notifications on mismatch
- API: `GET /api/device/active-session/`, `POST /api/device/rfid-scan/`, `POST /api/device/face-match/`, `POST /api/device/offline-batch/`
- System Health: device list with ID and API Key (after migration)
- Registration number: format, login with reg number, ID card, display in lists

---

## 🔴 Not implemented

### 1. Enrollment: save face embedding (backend)

- **Current:** Enroll form has a face panel with camera; captured image is sent as base64 in `face_capture`. **Backend does not read it or save it.**
- **Needed:** On submit, when `auth_method == 'face'` and `face_capture` is present:
  - Decode base64 → image
  - Run face detection + **embedding extraction** on the server
  - Store **only the embedding** (encrypted) in `BiometricEmbedding` (method=face)
- **Blocker:** Choice of **embedding model/length** must match what the **Pi will use**, so server and Pi use the same format (e.g. 128-D or 512-D, same library or compatible model).

### 2. Start session: optional course (UI)

- **Current:** “Start New Session” has only **Location**. Backend accepts `course_id` but the form does not send it, so sessions are often created without a course.
- **Needed for face+RFID:** Session should be linkable to a **course** (for 20‑min rule and reporting). Add an optional **Course** dropdown to the start-session form so the teacher can attach the session to a course when using the Pi at a classroom.

### 3. Show “on time” vs “late” in UI

- **Current:** `AttendanceRecord` has `status` (on_time/late) but no template shows it.
- **Needed:** Show status where attendance is listed:
  - Student: **My attendance history** (e.g. “On time” / “Late” badge per row)
  - Teacher: **Class attendance / roster / export** (e.g. status column, CSV column)
  - Reports: **Attendance reports** (e.g. status column or filter)
  - Parent: **Child’s attendance** (e.g. “On time” / “Late” per row)
- **CSV export:** Teacher export currently has: Student ID, Name, Email, Date/Time, Location, Session. Add a **Status** column (On time / Late).

### 4. Fingerprint panel (UI)

- **Current:** Placeholder text only.
- **Needed (optional):** Either keep as “coming later” or add a minimal message + “Skip” so the wizard is consistent. No backend change unless you add fingerprint hardware later.

---

## ❓ Questions for you (to clear requirements)

### A. Face embedding (enrollment + Pi)

1. **Embedding model:** Will the Pi use a specific library or model for face embedding (e.g. face_recognition, OpenCV + dlib, DeepFace, or something else)? The **server must use the same (or compatible) model and vector length** so that enrollment embeddings and Pi embeddings can be compared (e.g. 128-D or 512-D).
2. **If not decided yet:** Should we add a **placeholder** on the server (e.g. accept and store a fixed-size list of floats from the Pi for “face match,” and **skip** server-side embedding from the enrollment photo until you decide the model), or do you want to **decide the model now** and implement full enrollment → embedding → store in this sprint?
3. **Enrollment without face:** If the admin enrolls with auth method “Face” but does **not** capture a photo (e.g. skips the step), should we: (a) still create the user and allow adding face later from profile, or (b) require a captured face before submitting?

### B. Start session (teacher UI)

4. **Course in “Start session”:** Should the “Start New Session” form include an **optional “Course”** dropdown (in addition to Location)? That would let the teacher link the session to a course so the Pi’s session is clearly for that class and reports/20‑min rule use the right course. Or do you prefer sessions to be location-only and infer course elsewhere?

### C. On time / late in UI

5. **Where to show status:** Confirm we should show “On time” / “Late” in:
   - Student attendance history  
   - Teacher class/roster/export and reports  
   - Parent view of child’s attendance  
   Any other screens (e.g. dashboard cards, analytics)?

6. **Reports:** Do you want a **filter** like “Show only late” or “Show only on time” in the attendance reports page, or is a status column/badge enough?

### D. Pi / device

7. **Pi software:** Will you develop the Pi app (camera + RFID reader → call our API) yourself, or do you want a **minimal reference script** (e.g. Python) that: gets active session, sends RFID scan, sends face embedding (dummy or from a test library), so you can test the backend from a Pi?
8. **Device location:** When you register a Pi in System Health, you assign a **Location**. Should that be the **only** way the Pi is tied to a session (Pi at Location A gets the active session for Location A), or do you need a way to “assign” a session to a device by ID (e.g. teacher picks “Use device X for this session”)?

### E. Scope for this round

9. **Priority for this round:** What should we implement next?
   - **Option 1:** Enrollment: save face embedding (need your answer on embedding model / placeholder).
   - **Option 2:** UI only: start-session course dropdown, show on_time/late everywhere, CSV status column.
   - **Option 3:** Both (enrollment + UI), in that order or in parallel.
10. **Fingerprint:** Keep fingerprint panel as “coming in a future update” for now, or add a short message + “Skip” in the wizard?

---

Once you answer these, we can implement the chosen items and leave the rest for a later sprint.

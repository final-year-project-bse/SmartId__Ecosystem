# Face + RFID Attendance — Requirements & Design

Based on stakeholder answers. This document defines the flow for Raspberry Pi + RFID + camera attendance.

---

## 1. Hardware

| Item | Answer |
|------|--------|
| **1.1** RFID reader and camera | On the **same module** (one Raspberry Pi per entrance). |
| **1.2** Entrance points | One Pi can serve one door/entrance (number of Pis = number of doors as needed). |

---

## 2. Order and Timing

| Item | Requirement |
|------|-------------|
| **2.1** Order | **Strict order**: student must scan RFID first, then face is verified. Alternative approach (see below) uses a **pending-RFID queue** so we don’t rely on “next face = last RFID” when many enter together. |
| **2.2** Class time window | **20 minutes from class start**: |
| | • RFID + face verified **before** (session_start + 20 min) → mark attendance as **on-time (normal)**. |
| | • RFID + face verified **after** (session_start + 20 min) but still in session → mark attendance as **late**. |
| | Session has a start time (teacher starts session on web); Pi is linked to that session. |

---

## 3. Multiple Students (50–60, Enter Simultaneously)

- Students **scan RFID one by one** (or in quick succession) at the reader, then **can enter simultaneously** (many faces at once).
- **Approach — Pending-RFID queue:**
  - When a student scans RFID, add that **user** (and timestamp) to a **pending queue** for this Pi/session. No attendance yet.
  - Camera captures frames; for each **detected face** we compute an **embedding on the Pi** and send it to the server.
  - Server has a list of **pending RFIDs** for this device/session (e.g. last 2–3 minutes). Server matches the received **face embedding** against the **embeddings of all users in the pending queue** (1-to-N). Best match above threshold → mark that student’s attendance (on-time or late based on time), **remove that user from the pending queue**.
  - If multiple faces in one frame: send multiple embeddings (or process sequentially). Each face is matched to the **best-matching pending user**; each pending user is matched at most once per frame to avoid wrong assignment.
- This way we keep **strict order** (must have scanned RFID to be in the queue) without requiring **physical order** (we use face to resolve who is who among many).

---

## 4. Where Processing Runs

| Step | Where | What |
|------|--------|------|
| **4.1 At door (Pi)** | **Raspberry Pi** | Capture face image → compute **face embedding on Pi** → send **only embedding** (and device/session info) to server. No image sent for matching. |
| **4.2 Enrollment (web)** | **Server** | Browser captures photo → server receives image → server computes **face embedding** → store **only embedding** (encrypted) in DB. Server-side enrollment is preferred. |

---

## 5. Session / Class

| Item | Requirement |
|------|-------------|
| **5.1** How session is known | **Teacher starts a session** (e.g. on web dashboard) and the **Pi is linked to that session** (e.g. by device ID + session ID or location). So the Pi knows “current session” for this room/course. |
| **5.2** Same Pi, different rooms | Same Pi can be used for different rooms/courses at different times (session tells which course/room is active). |

---

## 6. Security and Edge Cases

| Item | Requirement |
|------|-------------|
| **6.1** Pi authentication | Pi **must authenticate** to the backend (e.g. **device ID + secret** or API key). Only registered devices can mark attendance. |
| **6.2** Face does not match RFID | **Notify teacher and admin** (e.g. in-app notification + optional email): “Possible card misuse at [location] – face did not match RFID user.” Do **not** mark attendance for that scan. |
| **6.3** Server unreachable | **Queue events on Pi** (RFID scan events + face embeddings with timestamps). When connection is back, **send queued data to server**; server **processes later** (mark on-time vs late using event timestamps vs session start + 20 min). |

---

## 7. Storage (Enrollment)

| Item | Requirement |
|------|-------------|
| **7.1** What to store | **Only face embeddings** (no full photo) for matching. No thumbnail required unless we add admin “view enrolled face” later. |
| **7.2** Faces per student | One face embedding per student (single reference). |

---

## 8. Data Flow Summary

1. **Enrollment (web)**  
   Admin/student enrolls; face photo captured → server computes embedding → store encrypted in `BiometricEmbedding` (method=face). RFID stored separately if applicable.

2. **Teacher starts session**  
   Teacher starts session for a course/location on web. Pi (by device ID) is associated with that session. Session has `started_at`. “On-time” cutoff = `started_at + 20 minutes`.

3. **At door (Pi online)**  
   - Student scans RFID → Pi sends “RFID scanned” event (user id or card id, device id, session id, timestamp) → server adds that user to **pending queue** for that session/device.  
   - Camera sees face(s) → Pi computes embedding(s) → Pi sends embedding(s) + device id + session id + timestamp.  
   - Server matches each embedding to **pending queue** (1-to-N), best match above threshold → mark attendance (on-time or late from timestamp), remove from queue. If no match or match below threshold → optionally log; if RFID was recent, consider “face mismatch” and notify teacher/admin.

4. **At door (Pi offline)**  
   Pi queues RFID events and face embeddings (with timestamps). When back online, Pi sends queue to server; server processes in order, computes on-time vs late from timestamps vs session start + 20 min, marks attendance and sends notifications as above.

5. **Device registration**  
   Each Pi is registered (e.g. in System Device table) with device ID and secret; API requires device auth for attendance endpoints.

---

## 9. Backend Work Needed (High Level)

- [x] **Device auth**: API key per Pi (`SystemDevice.api_key`); `X-Device-Id` + `X-Device-Key` headers; `IsDeviceAuthenticated` permission.
- [x] **Session linking**: Pi gets active session via `GET /api/device/active-session/` (by device location); Pi sends `session_id` in RFID/face requests.
- [ ] **Pending queue**: Store “pending RFID” per (session, device) with user_id and timestamp; TTL e.g. 3–5 minutes so old scans expire.
- [ ] **Face match endpoint**: Accept embedding + device_id + session_id + timestamp; match vs pending queue; mark attendance (on_time vs late); remove from queue; on mismatch notify teacher/admin.
- [ ] **Offline queue endpoint**: Accept batch of { rfid_events, face_events } from Pi; process in order; same logic for on-time/late and notifications.
- [ ] **Enrollment**: Save face embedding from photo (server-side); use existing or new pipeline for embedding extraction.
- [ ] **Attendance record**: Extend or use existing model to support “on_time” vs “late” (e.g. a flag or status field).

---

## 10. API Endpoints (Device / Pi)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/device/active-session/` | Get active session for this device's location. Headers: X-Device-Id, X-Device-Key. |
| POST | `/api/device/rfid-scan/` | Add RFID scan to pending queue. Body: session_id, rfid_tag, timestamp (optional). |
| POST | `/api/device/face-match/` | Send face embedding; match to pending; mark attendance. Body: session_id, embedding (list of floats), timestamp (optional). |
| POST | `/api/device/offline-batch/` | Send queued events when back online. Body: events list (type, session_id, timestamp, rfid_tag or embedding). |

---

*Document generated from stakeholder Q&A. Update this file when requirements or design change.*

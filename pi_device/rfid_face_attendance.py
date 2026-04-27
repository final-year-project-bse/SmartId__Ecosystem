"""
SmartID — Raspberry Pi: RFID + Face Recognition Attendance
===========================================================
Hardware required:
  • MFRC522 RFID reader  (SPI, GPIO 25 RST)
  • USB webcam or Pi Camera (V4L2)

Wiring (MFRC522 → Pi GPIO):
  SDA  → GPIO 8  (SPI CE0)
  SCK  → GPIO 11 (SPI SCLK)
  MOSI → GPIO 10 (SPI MOSI)
  MISO → GPIO 9  (SPI MISO)
  RST  → GPIO 25 (configurable in config.py)
  3.3V → Pin 1
  GND  → Pin 6

Install on Pi:
  pip install mfrc522 face_recognition opencv-python requests RPi.GPIO

Flow:
  1. Poll server for active session every 30 s.
  2. Wait for RFID scan → POST /api/device/rfid-scan/
  3. Capture face → compute 128-d embedding → POST /api/device/face-match/
  4. Show LED result; flush offline queue on reconnect.
"""
import sys
import time
import logging
import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Imports (fail early with helpful message) ──────────────────────────────
try:
    from mfrc522 import MFRC522
except ImportError:
    sys.exit("ERROR: Install mfrc522 →  pip install mfrc522")

try:
    import cv2
    import face_recognition
    import numpy as np
except ImportError:
    sys.exit("ERROR: Install face_recognition →  pip install face_recognition opencv-python")

import api_client as api
import gpio_feedback as led
from config import (
    RFID_RST_PIN, CAMERA_INDEX,
    FACE_CAPTURE_DELAY, FACE_UPSAMPLE,
)

# ── State ──────────────────────────────────────────────────────────────────
_running = True
_current_session = None
SESSION_REFRESH_INTERVAL = 30  # seconds


def _signal_handler(sig, frame):
    global _running
    log.info("Shutting down…")
    _running = False


signal.signal(signal.SIGINT,  _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ── RFID helpers ───────────────────────────────────────────────────────────

def read_rfid_tag(reader: MFRC522) -> str | None:
    """Block until a card is detected; return UID string or None on timeout."""
    (req_status, _) = reader.MFRC522_Request(reader.PICC_REQIDL)
    if req_status != reader.MI_OK:
        return None
    (uid_status, uid) = reader.MFRC522_Anticoll()
    if uid_status != reader.MI_OK:
        return None
    # UID is a list of ints; join as hex string for storage
    return "".join(f"{b:02X}" for b in uid)


# ── Face helpers ───────────────────────────────────────────────────────────

def capture_face_embedding() -> list | None:
    """
    Open camera, grab a frame, detect faces, return the first 128-d embedding.
    Returns None if no face detected.
    """
    cam = cv2.VideoCapture(CAMERA_INDEX)
    if not cam.isOpened():
        log.error("Cannot open camera index %d.", CAMERA_INDEX)
        return None
    try:
        # Discard first few frames (camera warm-up)
        for _ in range(5):
            cam.read()
        ret, frame = cam.read()
    finally:
        cam.release()

    if not ret or frame is None:
        log.warning("Camera read failed.")
        return None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, number_of_times_to_upsample=FACE_UPSAMPLE)
    if not locations:
        log.info("No face detected in frame.")
        return None

    encodings = face_recognition.face_encodings(rgb, locations)
    if not encodings:
        return None

    log.info("Face detected (%d in frame), using first.", len(encodings))
    return encodings[0].tolist()   # 128 floats


# ── Session management ────────────────────────────────────────────────────

def refresh_session():
    global _current_session
    sess = api.get_active_session()
    if sess:
        if not _current_session or sess["session_id"] != _current_session.get("session_id"):
            log.info("Active session: %s (id=%s)", sess.get("course_code", "No course"), sess["session_id"])
        _current_session = sess
    else:
        if _current_session:
            log.info("No active session — waiting…")
        _current_session = None


# ── Main loop ─────────────────────────────────────────────────────────────

def main():
    led.setup()
    log.info("SmartID RFID+Face attendance starting…")
    log.info("Flushing offline queue…")
    api.flush_offline_queue()

    reader = MFRC522()
    last_session_check = 0
    last_rfid_uid = None
    last_rfid_time = 0
    DEBOUNCE_SECONDS = 3  # ignore same card within 3 s

    try:
        while _running:
            # Periodically refresh session
            now = time.time()
            if now - last_session_check > SESSION_REFRESH_INTERVAL:
                refresh_session()
                last_session_check = now
                if _current_session is None:
                    time.sleep(2)
                    continue

            if _current_session is None:
                time.sleep(0.5)
                continue

            session_id = _current_session["session_id"]

            # ── Step 1: Wait for RFID ──────────────────────────────────────
            tag = read_rfid_tag(reader)
            if tag is None:
                time.sleep(0.1)
                continue

            now = time.time()
            if tag == last_rfid_uid and (now - last_rfid_time) < DEBOUNCE_SECONDS:
                time.sleep(0.2)
                continue
            last_rfid_uid = tag
            last_rfid_time = now

            log.info("RFID scan: %s", tag)
            rfid_result = api.post_rfid_scan(session_id, tag)

            if rfid_result.get("offline"):
                log.warning("Server offline — RFID queued.")
                led.failure()
                time.sleep(1)
                continue

            if not rfid_result.get("success"):
                log.warning("RFID not recognised: %s", rfid_result.get("error", ""))
                led.failure()
                time.sleep(1)
                continue

            log.info("RFID OK → %s. Waiting %.1fs for face…",
                     rfid_result.get("institutional_id"), FACE_CAPTURE_DELAY)
            time.sleep(FACE_CAPTURE_DELAY)

            # ── Step 2: Capture & match face ──────────────────────────────
            embedding = capture_face_embedding()
            if embedding is None:
                log.warning("No face captured — attendance NOT marked.")
                led.failure()
                continue

            face_result = api.post_face_match(session_id, embedding)

            if face_result.get("offline"):
                log.warning("Server offline — face embedding queued.")
                led.failure()
                continue

            if face_result.get("success") and face_result.get("matched"):
                status_label = face_result.get("status", "")
                user_id_str = face_result.get("institutional_id", "")
                log.info("Attendance marked (%s) for %s.", status_label, user_id_str)
                if face_result.get("already_recorded") or not face_result.get("matched"):
                    led.already_recorded()
                else:
                    led.success()
            else:
                log.warning("Face did not match RFID — possible card misuse. Result: %s", face_result)
                led.failure()

            time.sleep(0.5)

    finally:
        led.cleanup()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    main()

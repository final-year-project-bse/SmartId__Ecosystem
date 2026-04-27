"""
SmartID — Raspberry Pi: Fingerprint Attendance (AS608 / R307)
=============================================================
Hardware required:
  • AS608 or R307 optical fingerprint sensor (UART)

Wiring (AS608 → Pi):
  VCC   → 3.3 V (Pin 1) or 5 V (Pin 2) — check your module
  GND   → GND (Pin 6)
  TX    → GPIO 15 / RXD (Pin 10)   ← sensor TX to Pi RX
  RX    → GPIO 14 / TXD (Pin 8)    ← sensor RX to Pi TX

  If using /dev/ttyAMA0 you may need to disable the Pi serial console:
    sudo raspi-config → Interface Options → Serial → disable login shell, enable hardware serial.
  Or use a USB-to-UART adapter → /dev/ttyUSB0 (no config needed).

Install on Pi:
  pip install pyfingerprint requests RPi.GPIO

Enroll fingerprints first using fingerprint_enroll.py, then run this script
to start the attendance loop.

Flow:
  1. Poll server for active session.
  2. Prompt student to place finger on sensor.
  3. Sensor matches internally and returns slot position + confidence.
  4. POST /api/device/fingerprint-scan/ → server marks attendance.
  5. LED feedback.
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

try:
    from pyfingerprint.pyfingerprint import PyFingerprint, FINGERPRINT_CHARBUFFER1
except ImportError:
    sys.exit("ERROR: Install pyfingerprint →  pip install pyfingerprint")

import api_client as api
import gpio_feedback as led
from config import (
    FINGERPRINT_PORT, FINGERPRINT_BAUD,
    FINGERPRINT_PASSWORD, FINGERPRINT_ADDRESS,
    FINGERPRINT_MIN_CONFIDENCE,
)

_running = True
_current_session = None
SESSION_REFRESH_INTERVAL = 30


def _signal_handler(sig, frame):
    global _running
    log.info("Shutting down…")
    _running = False


signal.signal(signal.SIGINT,  _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def init_sensor() -> PyFingerprint:
    """Initialise and verify sensor password."""
    try:
        f = PyFingerprint(
            FINGERPRINT_PORT,
            FINGERPRINT_BAUD,
            FINGERPRINT_ADDRESS,
            FINGERPRINT_PASSWORD,
        )
    except Exception as e:
        sys.exit(f"ERROR: Cannot open fingerprint sensor on {FINGERPRINT_PORT}: {e}")

    if not f.verifyPassword():
        sys.exit("ERROR: Wrong fingerprint sensor password. Check FINGERPRINT_PASSWORD in config.py.")

    cap = f.getStorageCapacity()
    used = f.getTemplateCount()
    log.info("Sensor ready — %d/%d slots used.", used, cap)
    return f


def wait_for_finger(sensor: PyFingerprint, timeout_s: float = 10.0) -> bool:
    """Return True when a finger is placed, False on timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if sensor.readImage():
            return True
        time.sleep(0.1)
    return False


def scan_and_match(sensor: PyFingerprint):
    """
    Read finger image, convert to template, search sensor storage.
    Returns (slot_position, confidence) or (None, 0) on failure.
    """
    if not sensor.readImage():
        return None, 0

    sensor.convertImage(FINGERPRINT_CHARBUFFER1)

    result = sensor.searchTemplate()
    slot_position = result[0]
    confidence    = result[1]

    if slot_position == -1:
        log.info("Finger not recognised (no match in sensor).")
        return None, 0

    if confidence < FINGERPRINT_MIN_CONFIDENCE:
        log.info("Match score %d below threshold %d — rejected.", confidence, FINGERPRINT_MIN_CONFIDENCE)
        return None, 0

    return slot_position, confidence


def refresh_session():
    global _current_session
    sess = api.get_active_session()
    if sess:
        if not _current_session or sess["session_id"] != _current_session.get("session_id"):
            log.info("Active session: %s (id=%s)", sess.get("course_code", "?"), sess["session_id"])
        _current_session = sess
    else:
        if _current_session:
            log.info("No active session — waiting…")
        _current_session = None


def main():
    led.setup()
    log.info("SmartID Fingerprint attendance starting…")
    api.flush_offline_queue()

    sensor = init_sensor()
    last_session_check = 0

    try:
        while _running:
            now = time.time()
            if now - last_session_check > SESSION_REFRESH_INTERVAL:
                refresh_session()
                last_session_check = now

            if _current_session is None:
                time.sleep(2)
                continue

            session_id = _current_session["session_id"]

            log.info("Place finger on sensor…")
            if not wait_for_finger(sensor, timeout_s=5):
                time.sleep(0.2)
                continue

            slot, confidence = scan_and_match(sensor)
            if slot is None:
                log.warning("No match — unrecognised finger.")
                led.failure()
                time.sleep(1)
                continue

            log.info("Matched slot %d (confidence %d). Sending to server…", slot, confidence)
            result = api.post_fingerprint_scan(session_id, slot, confidence)

            if result.get("success"):
                if result.get("already_recorded"):
                    log.info("Already recorded for %s.", result.get("institutional_id", ""))
                    led.already_recorded()
                else:
                    log.info("Attendance marked (%s) for %s.",
                             result.get("status", ""), result.get("institutional_id", ""))
                    led.success()
            else:
                log.warning("Server rejected scan: %s", result.get("error", result))
                led.failure()

            time.sleep(1.5)  # debounce

    finally:
        led.cleanup()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    main()

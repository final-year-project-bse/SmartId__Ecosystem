"""
SmartID — Raspberry Pi: Fingerprint Enrollment Utility
======================================================
Run this on the Pi (as admin) to enroll a student's fingerprint.
Stores the template in the sensor's flash and reports the slot to the server.

Usage:
  python fingerprint_enroll.py --id SP2022-001          # by institutional ID
  python fingerprint_enroll.py --user-id 5              # by Django user pk
  python fingerprint_enroll.py --id SP2022-001 --slot 3  # force a specific slot

Steps performed:
  1. Ask student to place finger twice (sensor stores template in flash)
  2. POST /api/device/fingerprint-enroll/ to link slot → user in Django DB
"""
import sys
import time
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

try:
    from pyfingerprint.pyfingerprint import (
        PyFingerprint,
        FINGERPRINT_CHARBUFFER1,
        FINGERPRINT_CHARBUFFER2,
    )
except ImportError:
    sys.exit("Install pyfingerprint:  pip install pyfingerprint")

from config import (
    SERVER_URL, DEVICE_ID, DEVICE_KEY,
    FINGERPRINT_PORT, FINGERPRINT_BAUD,
    FINGERPRINT_PASSWORD, FINGERPRINT_ADDRESS,
)


# ── API call ───────────────────────────────────────────────────────────────

def register_slot(user_id=None, institutional_id=None, slot_position=None):
    headers = {"X-Device-Id": str(DEVICE_ID), "X-Device-Key": DEVICE_KEY}
    payload = {"slot_position": slot_position}
    if user_id:
        payload["user_id"] = user_id
    else:
        payload["institutional_id"] = institutional_id

    url = f"{SERVER_URL.rstrip('/')}/api/device/fingerprint-enroll/"
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        return r.status_code, r.json()
    except requests.RequestException as e:
        return None, {"error": str(e)}


# ── Sensor helpers ─────────────────────────────────────────────────────────

def wait_for_finger(sensor, prompt: str):
    print(prompt)
    while True:
        if sensor.readImage():
            return
        time.sleep(0.1)


def wait_for_removal(sensor):
    print("  Remove finger…")
    time.sleep(0.5)
    while sensor.readImage():
        time.sleep(0.1)
    print("  Finger removed.")


def enroll_finger(sensor: PyFingerprint, slot: int = None) -> int:
    """
    Enroll fingerprint into the sensor.
    If slot is None, sensor picks the first free slot.
    Returns the slot position used.
    """
    # First scan
    wait_for_finger(sensor, "\n[1/2] Place finger on sensor…")
    sensor.convertImage(FINGERPRINT_CHARBUFFER1)
    wait_for_removal(sensor)

    # Second scan (same finger)
    wait_for_finger(sensor, "[2/2] Place the SAME finger again…")
    sensor.convertImage(FINGERPRINT_CHARBUFFER2)

    if sensor.compareCharacteristics() == 0:
        raise ValueError("Fingers do not match — please try again.")

    sensor.createTemplate()

    if slot is not None:
        position = sensor.storeTemplate(slot)
    else:
        position = sensor.storeTemplate()

    return position


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SmartID fingerprint enrollment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id",      metavar="INST_ID",  help="Student institutional ID (e.g. SP2022-001)")
    group.add_argument("--user-id", metavar="INT",      type=int, help="Django user pk")
    parser.add_argument("--slot",   metavar="0-127",    type=int, default=None,
                        help="Force a specific sensor slot (default: auto-assign)")
    args = parser.parse_args()

    # Sensor init
    try:
        sensor = PyFingerprint(
            FINGERPRINT_PORT, FINGERPRINT_BAUD,
            FINGERPRINT_ADDRESS, FINGERPRINT_PASSWORD,
        )
    except Exception as e:
        sys.exit(f"Cannot open sensor on {FINGERPRINT_PORT}: {e}")

    if not sensor.verifyPassword():
        sys.exit("Wrong sensor password. Check FINGERPRINT_PASSWORD in config.py.")

    used = sensor.getTemplateCount()
    cap  = sensor.getStorageCapacity()
    print(f"Sensor ready — {used}/{cap} slots used.")

    if args.slot is not None and not (0 <= args.slot <= 127):
        sys.exit("Slot must be 0-127.")

    # Enroll
    try:
        slot_position = enroll_finger(sensor, slot=args.slot)
    except ValueError as e:
        sys.exit(f"Enrollment failed: {e}")
    except Exception as e:
        sys.exit(f"Sensor error: {e}")

    print(f"\nFingerprint stored in sensor slot {slot_position}.")
    print("Registering with server…")

    code, data = register_slot(
        user_id=args.user_id,
        institutional_id=args.id,
        slot_position=slot_position,
    )

    if code == 201:
        print(f"SUCCESS: Slot {slot_position} registered for {data.get('institutional_id', '?')}.")
    elif code == 409:
        print(f"CONFLICT: {data.get('error', data)}")
        print(f"Hint: delete the old enrollment first, then re-run.")
    else:
        print(f"Server error ({code}): {data}")
        print(f"Slot {slot_position} is stored in sensor but NOT linked in DB — retry register_slot manually.")


if __name__ == "__main__":
    main()

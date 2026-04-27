"""
Shared HTTP client for all Pi scripts.
Handles auth headers, retries, and the offline queue.
"""
import json
import time
import logging
import requests

from config import SERVER_URL, DEVICE_ID, DEVICE_KEY, OFFLINE_QUEUE_FILE

log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "X-Device-Id":  str(DEVICE_ID),
    "X-Device-Key": DEVICE_KEY,
    "Content-Type": "application/json",
})
TIMEOUT = 8  # seconds


def _url(path: str) -> str:
    return f"{SERVER_URL.rstrip('/')}/api/{path.lstrip('/')}"


def send_heartbeat():
    """Update device status on server; call every ~60 s."""
    try:
        r = SESSION.post(_url("device/heartbeat/"), timeout=TIMEOUT)
        return r.status_code == 200
    except requests.RequestException:
        return False


def get_active_session():
    """Return active session dict or None."""
    try:
        r = SESSION.get(_url("device/active-session/"), timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException as e:
        log.warning("get_active_session failed: %s", e)
    return None


def post_rfid_scan(session_id: int, rfid_tag: str, timestamp: str = None) -> dict:
    payload = {"session_id": session_id, "rfid_tag": rfid_tag}
    if timestamp:
        payload["timestamp"] = timestamp
    try:
        r = SESSION.post(_url("device/rfid-scan/"), json=payload, timeout=TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        log.warning("post_rfid_scan offline: %s", e)
        _queue_event({"type": "rfid_scan", "session_id": session_id,
                      "rfid_tag": rfid_tag, "timestamp": timestamp or _now_iso()})
        return {"success": False, "offline": True}


def post_face_match(session_id: int, embedding: list, timestamp: str = None) -> dict:
    payload = {"session_id": session_id, "embedding": embedding}
    if timestamp:
        payload["timestamp"] = timestamp
    try:
        r = SESSION.post(_url("device/face-match/"), json=payload, timeout=TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        log.warning("post_face_match offline: %s", e)
        _queue_event({"type": "face_match", "session_id": session_id,
                      "embedding": embedding, "timestamp": timestamp or _now_iso()})
        return {"success": False, "offline": True}


def post_fingerprint_scan(session_id: int, slot_position: int,
                          confidence: int = 0, timestamp: str = None) -> dict:
    payload = {"session_id": session_id, "slot_position": slot_position,
               "confidence": confidence}
    if timestamp:
        payload["timestamp"] = timestamp
    try:
        r = SESSION.post(_url("device/fingerprint-scan/"), json=payload, timeout=TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        log.warning("post_fingerprint_scan failed: %s", e)
        return {"success": False, "error": str(e)}


def flush_offline_queue():
    """Send queued events to /api/device/offline-batch/ and clear file on success."""
    try:
        with open(OFFLINE_QUEUE_FILE, "r") as f:
            events = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    if not events:
        return

    try:
        r = SESSION.post(_url("device/offline-batch/"), json={"events": events}, timeout=30)
        if r.status_code == 200:
            log.info("Flushed %d offline events.", len(events))
            with open(OFFLINE_QUEUE_FILE, "w") as f:
                json.dump([], f)
        else:
            log.warning("Offline batch returned %s: %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        log.warning("flush_offline_queue failed: %s", e)


def _queue_event(event: dict):
    try:
        try:
            with open(OFFLINE_QUEUE_FILE, "r") as f:
                events = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            events = []
        events.append(event)
        with open(OFFLINE_QUEUE_FILE, "w") as f:
            json.dump(events, f)
    except Exception as e:
        log.error("Could not write to offline queue: %s", e)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

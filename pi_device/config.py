"""
Raspberry Pi device configuration.
Edit these values before deploying to the Pi.

How to get DEVICE_ID and DEVICE_KEY:
  1. Admin logs in → System Settings → Register Device
  2. Copy the generated Device ID and API Key here.
"""

# ── Server connection ──────────────────────────────────────────────────────
SERVER_URL = "http://192.168.1.100:8000"   # Change to your server's IP/domain
DEVICE_ID  = 1                             # SystemDevice.pk from admin dashboard
DEVICE_KEY = "your-64-char-api-key-here"  # SystemDevice.api_key from admin dashboard

# ── RFID (MFRC522 via SPI) ────────────────────────────────────────────────
RFID_SPI_BUS  = 0
RFID_SPI_DEV  = 0
RFID_RST_PIN  = 25   # BCM GPIO pin for MFRC522 RST

# ── Camera (face recognition) ─────────────────────────────────────────────
CAMERA_INDEX       = 0     # 0 = first USB cam / Pi Camera via V4L2
FACE_CAPTURE_DELAY = 1.5   # seconds to wait after RFID scan before capturing face
FACE_UPSAMPLE      = 1     # face_recognition upsample (1 = faster, 2 = more accurate)

# ── Fingerprint sensor (AS608 / R307 via UART) ────────────────────────────
FINGERPRINT_PORT     = "/dev/ttyUSB0"   # or /dev/ttyAMA0 for hardware UART
FINGERPRINT_BAUD     = 57600
FINGERPRINT_PASSWORD = 0x00000000       # sensor password (default = 0)
FINGERPRINT_ADDRESS  = 0xFFFFFFFF       # sensor address  (default = 0xFFFFFFFF)
FINGERPRINT_MIN_CONFIDENCE = 50         # reject matches below this score (0-300)

# ── Offline queue ─────────────────────────────────────────────────────────
OFFLINE_QUEUE_FILE = "/tmp/smartid_offline_queue.json"

# ── GPIO feedback LEDs (BCM pin numbers, set to None to disable) ──────────
LED_GREEN = 17   # attendance marked successfully
LED_RED   = 27   # scan failed / not recognised
LED_BUZZ  = None # optional buzzer pin

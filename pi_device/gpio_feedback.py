"""
LED / buzzer feedback helpers.
Safe to import on non-Pi machines (falls back to print).
"""
import time
import logging

log = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except ImportError:
    _HAS_GPIO = False
    log.warning("RPi.GPIO not available — LED feedback disabled.")

from config import LED_GREEN, LED_RED, LED_BUZZ


def setup():
    if not _HAS_GPIO:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in (LED_GREEN, LED_RED, LED_BUZZ):
        if pin is not None:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)


def cleanup():
    if _HAS_GPIO:
        GPIO.cleanup()


def blink(pin, times=2, on_ms=200, off_ms=150):
    if not _HAS_GPIO or pin is None:
        return
    for _ in range(times):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(on_ms / 1000)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(off_ms / 1000)


def success():
    """Green LED blink — attendance marked."""
    blink(LED_GREEN, times=2)
    blink(LED_BUZZ, times=1, on_ms=100)


def failure():
    """Red LED blink — scan failed / unknown card."""
    blink(LED_RED, times=3, on_ms=300)


def already_recorded():
    """Single green blink — already marked today."""
    blink(LED_GREEN, times=1, on_ms=500)

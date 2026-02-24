"""
Performance & security middleware for the SmartID Ecosystem.
"""
import time
import logging

logger = logging.getLogger('smartid.performance')


class QueryTimingMiddleware:
    """
    Measures total request wall-clock time and logs a warning if a dashboard
    route exceeds 3 seconds (SRS performance requirement — NFR-P2).
    Adds an `X-Request-Time-Ms` header to every response for observability.
    """
    THRESHOLD_MS = 3000  # 3 seconds per SRS

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)

        response['X-Request-Time-Ms'] = str(elapsed_ms)

        if elapsed_ms > self.THRESHOLD_MS:
            logger.warning(
                'SLOW REQUEST [%s %s] — %.1f ms (threshold: %d ms)',
                request.method, request.path, elapsed_ms, self.THRESHOLD_MS,
            )

        return response

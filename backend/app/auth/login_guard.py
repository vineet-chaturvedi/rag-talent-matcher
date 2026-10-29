"""
Brute-force protection for the login endpoint (Step 9).

After MAX_FAILURES wrong passwords for one email within WINDOW, further attempts for that email are
refused for the rest of the window (HTTP 429). This is kept in memory: simple, and enough for one server.
With several servers you'd keep these counters in Redis, and add per-IP limits at the gateway.
"""
import time

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

_failures: dict[str, list[float]] = {}     # email -> timestamps of recent failures


def _recent(email: str) -> list[float]:
    cutoff = time.monotonic() - WINDOW_SECONDS
    times = [t for t in _failures.get(email, []) if t > cutoff]
    _failures[email] = times
    return times


def seconds_locked(email: str) -> int:
    """0 if login may be attempted, else seconds until the lock ends."""
    times = _recent(email)
    if len(times) < MAX_FAILURES:
        return 0
    return max(1, int(times[0] + WINDOW_SECONDS - time.monotonic()))


def record_failure(email: str) -> None:
    _recent(email).append(time.monotonic())


def record_success(email: str) -> None:
    _failures.pop(email, None)

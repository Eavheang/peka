import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# Per-process fallback limiter; put a shared limiter at the gateway if the
# service runs with multiple replicas.
LOGIN_ATTEMPT_LIMIT = 10
LOGIN_ATTEMPT_WINDOW_SECONDS = 60

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def login_rate_limiter(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        if len(_attempts) >= 10_000:
            for key in [k for k, v in _attempts.items() if not v or now - v[-1] >= LOGIN_ATTEMPT_WINDOW_SECONDS]:
                del _attempts[key]
        attempts = _attempts[client]
        while attempts and now - attempts[0] >= LOGIN_ATTEMPT_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
            raise HTTPException(status_code=429, detail="Too many login attempts",
                                headers={"Retry-After": str(LOGIN_ATTEMPT_WINDOW_SECONDS)})
        attempts.append(now)


def reset() -> None:
    with _lock:
        _attempts.clear()

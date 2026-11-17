"""Whether the server can reach the internet. Web search, Google Drive and invitation email need it."""
import socket
import threading
import time

_CACHE_SECONDS = 30
_PROBE = ("1.1.1.1", 443)
# Start optimistic: requests racing the first probe act as online rather than flash "offline".
_last_check: tuple[float, bool] = (float("-inf"), True)
_probing = threading.Lock()


def is_online() -> bool:
    global _last_check
    checked_at, online = _last_check
    # One request probes when the cache expires; the others keep the last answer instead of waiting.
    if time.monotonic() - checked_at < _CACHE_SECONDS or not _probing.acquire(blocking=False):
        return online
    try:
        socket.create_connection(_PROBE, timeout=2).close()
        online = True
    except OSError:
        online = False
    finally:
        _probing.release()
    _last_check = (time.monotonic(), online)
    return online

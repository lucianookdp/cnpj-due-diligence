import threading
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request

_lock = threading.Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int, window_seconds: int) -> Callable[[Request], None]:
    """Simple in-memory fixed-window limiter keyed by (client IP, path).

    Single-process only — state isn't shared across workers/replicas. Fine at
    this app's current scale (one backend container); move to a shared store
    (e.g. Postgres-backed, matching the rest of the stack) before running
    multiple instances. If deployed behind a reverse proxy, the proxy must
    forward the real client IP and uvicorn must run with --proxy-headers, or
    every client appears to share the proxy's IP and gets rate-limited together.
    """

    def dependency(request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"
        now = time.monotonic()

        with _lock:
            bucket = _buckets[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.pop(0)
            if len(bucket) >= max_requests:
                raise HTTPException(
                    status_code=429, detail="Muitas tentativas. Tente novamente mais tarde."
                )
            bucket.append(now)

    return dependency

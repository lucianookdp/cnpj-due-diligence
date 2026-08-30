import time
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

import app.core.rate_limit as rate_limit_module
from app.core.rate_limit import rate_limit


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets():
    # _buckets is module-level global state, shared across every call to
    # rate_limit() regardless of which test made it — without this reset,
    # tests leak request counts into each other via matching (ip, path) keys.
    rate_limit_module._buckets.clear()
    yield


def _request(ip: str = "1.2.3.4", path: str = "/auth/login") -> Mock:
    request = Mock()
    request.client.host = ip
    request.url.path = path
    return request


def test_allows_requests_under_the_limit():
    dependency = rate_limit(max_requests=3, window_seconds=60)
    request = _request()

    for _ in range(3):
        dependency(request)  # should not raise


def test_blocks_requests_over_the_limit():
    dependency = rate_limit(max_requests=3, window_seconds=60)
    request = _request()

    for _ in range(3):
        dependency(request)

    with pytest.raises(HTTPException) as exc_info:
        dependency(request)
    assert exc_info.value.status_code == 429


def test_tracks_different_ips_independently():
    dependency = rate_limit(max_requests=1, window_seconds=60)

    dependency(_request(ip="1.1.1.1"))
    dependency(_request(ip="2.2.2.2"))  # different IP, should not raise


def test_tracks_different_paths_independently():
    dependency = rate_limit(max_requests=1, window_seconds=60)

    dependency(_request(path="/auth/login"))
    dependency(_request(path="/auth/register"))  # different path, should not raise


def test_allows_requests_again_after_window_expires():
    dependency = rate_limit(max_requests=1, window_seconds=0.05)
    request = _request()

    dependency(request)
    time.sleep(0.1)
    dependency(request)  # window expired, should not raise


def test_handles_missing_client_gracefully():
    dependency = rate_limit(max_requests=1, window_seconds=60)
    request = Mock()
    request.client = None
    request.url.path = "/auth/login"

    dependency(request)  # should not raise (falls back to "unknown" key)

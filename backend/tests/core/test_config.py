import pytest

from app.core.config import DEV_SECRET_KEY, Settings, assert_production_ready


def test_raises_when_production_with_default_secret():
    settings = Settings(environment="production", secret_key=DEV_SECRET_KEY)

    with pytest.raises(RuntimeError):
        assert_production_ready(settings)


def test_allows_default_secret_in_development():
    settings = Settings(environment="development", secret_key=DEV_SECRET_KEY)

    assert_production_ready(settings)


def test_allows_production_with_real_secret():
    settings = Settings(environment="production", secret_key="a" * 32)

    assert_production_ready(settings)


def test_raises_when_production_with_short_but_non_default_secret():
    # Not the literal placeholder, but still too weak for HS256 — must not
    # slip past just because it isn't DEV_SECRET_KEY verbatim.
    settings = Settings(environment="production", secret_key="mypassword123")

    with pytest.raises(RuntimeError):
        assert_production_ready(settings)

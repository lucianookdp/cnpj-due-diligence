from unittest.mock import patch

import bcrypt

from app.core.security import hash_password, verify_password_timing_safe


def test_accepts_correct_password():
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password_timing_safe("correct-horse-battery-staple", hashed) is True


def test_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password_timing_safe("wrong-password", hashed) is False


def test_rejects_and_still_hashes_when_no_user_exists():
    """The whole point of this function: a nonexistent user must still cost
    a real bcrypt.checkpw call, or login response times leak which emails
    are registered.
    """
    with patch("app.core.security.bcrypt.checkpw", wraps=bcrypt.checkpw) as spy:
        result = verify_password_timing_safe("whatever", None)

    assert result is False
    spy.assert_called_once()

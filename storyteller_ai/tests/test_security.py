import pytest

from backend.services.security import is_loopback_host, validate_public_narration


def test_loopback_and_secret_guards():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("::1")
    assert not is_loopback_host("192.168.1.10")
    validate_public_narration("The rain starts.", ["hidden identity"])
    with pytest.raises(ValueError):
        validate_public_narration("The hidden identity is revealed.", ["hidden identity"])
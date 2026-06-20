import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def configure_test_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-jwt-secret-key")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()

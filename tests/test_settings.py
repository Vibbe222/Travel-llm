import pytest

from settings import SettingsError, get_settings


def test_settings_defaults_are_development_safe(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    monkeypatch.setenv("AMAP_API_KEY", "")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("REQUIRE_API_KEYS", raising=False)

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.model_name == "deepseek-v4-flash"
    assert "*" not in settings.cors_origins
    assert settings.require_api_keys is False
    assert settings.cache_enabled is True
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.redis_checkpoint_enabled is True


def test_settings_rejects_wildcard_cors_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake")
    monkeypatch.setenv("AMAP_API_KEY", "fake")

    with pytest.raises(SettingsError, match="CORS_ORIGINS"):
        get_settings()


def test_settings_requires_api_keys_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://travel.example.com")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    monkeypatch.setenv("AMAP_API_KEY", "")
    monkeypatch.delenv("REQUIRE_API_KEYS", raising=False)

    with pytest.raises(SettingsError, match="DASHSCOPE_API_KEY"):
        get_settings()


def test_settings_allows_explicit_development_wildcard_cors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    settings = get_settings()

    assert settings.cors_origins == ("*",)


def test_env_example_documents_required_configuration():
    content = open(".env.example", encoding="utf-8").read()

    for name in [
        "APP_ENV",
        "MODEL_NAME",
        "DASHSCOPE_BASE_URL",
        "DASHSCOPE_API_KEY",
        "AMAP_API_KEY",
        "REQUEST_TIMEOUT_SECONDS",
        "CACHE_ENABLED",
        "CACHE_TTL_SECONDS",
        "REDIS_URL",
        "REDIS_KEY_PREFIX",
        "REDIS_CHECKPOINT_ENABLED",
        "REDIS_CHECKPOINT_TTL_SECONDS",
        "CORS_ORIGINS",
        "LOG_LEVEL",
    ]:
        assert name in content

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv


TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}
FALSY_VALUES = {"0", "false", "no", "n", "off"}
VALID_APP_ENVS = {"development", "testing", "production"}


class SettingsError(ValueError):
    """Raised when runtime configuration is invalid."""


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_int(name: str, default: int) -> int:
    raw = _get_env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer, got {raw!r}") from exc


def _get_float(name: str, default: float) -> float:
    raw = _get_env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be a number, got {raw!r}") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = _get_env(name)
    if not raw:
        return default
    normalized = raw.lower()
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    raise SettingsError(f"{name} must be a boolean value, got {raw!r}")


def _get_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = _get_env(name)
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str
    model_name: str
    dashscope_base_url: str
    dashscope_api_key: str
    amap_api_key: str
    request_timeout_seconds: int
    max_retries: int
    cache_enabled: bool
    cache_ttl_seconds: int
    log_level: str
    cors_origins: tuple[str, ...]
    cors_allow_credentials: bool
    require_api_keys: bool
    redis_url: str
    redis_key_prefix: str
    redis_checkpoint_enabled: bool
    redis_checkpoint_ttl_seconds: int

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate(self) -> None:
        errors: list[str] = []

        if self.app_env not in VALID_APP_ENVS:
            errors.append(
                f"APP_ENV must be one of {sorted(VALID_APP_ENVS)}, got {self.app_env!r}"
            )

        if not self.model_name:
            errors.append("MODEL_NAME must not be empty")

        if not self.dashscope_base_url:
            errors.append("DASHSCOPE_BASE_URL must not be empty")

        if self.request_timeout_seconds <= 0:
            errors.append("REQUEST_TIMEOUT_SECONDS must be greater than 0")

        if self.max_retries < 0:
            errors.append("MAX_RETRIES must be greater than or equal to 0")

        if self.cache_ttl_seconds <= 0:
            errors.append("CACHE_TTL_SECONDS must be greater than 0")

        if not self.cors_origins:
            errors.append("CORS_ORIGINS must contain at least one origin")

        if self.is_production and "*" in self.cors_origins:
            errors.append('CORS_ORIGINS must not contain "*" when APP_ENV=production')

        if self.require_api_keys:
            if not self.dashscope_api_key:
                errors.append("DASHSCOPE_API_KEY is required")
            if not self.amap_api_key:
                errors.append("AMAP_API_KEY is required")

        if not hasattr(logging, self.log_level):
            errors.append(f"LOG_LEVEL is not recognized: {self.log_level!r}")

        if not self.redis_url:
            errors.append("REDIS_URL must not be empty")

        if not self.redis_key_prefix:
            errors.append("REDIS_KEY_PREFIX must not be empty")

        if self.redis_checkpoint_ttl_seconds <= 0:
            errors.append("REDIS_CHECKPOINT_TTL_SECONDS must be greater than 0")

        if errors:
            raise SettingsError("; ".join(errors))


def _build_settings() -> Settings:
    load_dotenv(find_dotenv())
    app_env = _get_env("APP_ENV", "development").lower()

    settings = Settings(
        app_env=app_env,
        model_name=_get_env("MODEL_NAME", "deepseek-v4-flash"),
        dashscope_base_url=_get_env(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        dashscope_api_key=_get_env("DASHSCOPE_API_KEY"),
        amap_api_key=_get_env("AMAP_API_KEY"),
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 12),
        max_retries=_get_int("MAX_RETRIES", 2),
        cache_enabled=_get_bool("CACHE_ENABLED", True),
        cache_ttl_seconds=_get_int("CACHE_TTL_SECONDS", 86400),
        log_level=_get_env("LOG_LEVEL", "INFO").upper(),
        cors_origins=_get_csv(
            "CORS_ORIGINS",
            (
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ),
        ),
        cors_allow_credentials=_get_bool("CORS_ALLOW_CREDENTIALS", True),
        require_api_keys=_get_bool("REQUIRE_API_KEYS", app_env == "production"),
        redis_url=_get_env("REDIS_URL", "redis://127.0.0.1:6379/0"),
        redis_key_prefix=_get_env("REDIS_KEY_PREFIX", "travel_llm"),
        redis_checkpoint_enabled=_get_bool("REDIS_CHECKPOINT_ENABLED", True),
        redis_checkpoint_ttl_seconds=_get_int("REDIS_CHECKPOINT_TTL_SECONDS", 604800),
    )
    settings.validate()
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _build_settings()


def reload_settings_for_tests() -> Settings:
    get_settings.cache_clear()
    return get_settings()

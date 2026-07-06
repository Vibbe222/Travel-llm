import logging
import os
import time
from typing import Any

import requests

DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = (1, 2)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_REQUEST_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)

_LOGGING_CONFIGURED = False


def ok(data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
    }


def fail(message: str, detail: Any = None, retryable: bool = False) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "error": {
            "message": message,
            "detail": detail,
            "retryable": retryable,
        },
    }


def configure_logging_from_env() -> None:
    global _LOGGING_CONFIGURED
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if not _LOGGING_CONFIGURED:
        logging.basicConfig(
            level=level,
            format="%(levelname)s %(name)s %(message)s",
        )
        _LOGGING_CONFIGURED = True
    else:
        logging.getLogger().setLevel(level)


def get_tool_logger(tool_name: str) -> logging.Logger:
    configure_logging_from_env()
    return logging.getLogger(f"travel_llm.tools.{tool_name}")


def summarize_params(params: dict[str, Any], allowed_keys: tuple[str, ...]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in params:
            continue
        value = params[key]
        if isinstance(value, str):
            summary[key] = value[:80]
        else:
            summary[key] = value
    return summary


def is_retryable_http_status(status_code: int | None) -> bool:
    return status_code in RETRYABLE_HTTP_STATUS


def request_json_with_retry(
    *,
    tool_name: str,
    url: str,
    params: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    safe_log_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger = get_tool_logger(tool_name)
    attempts = max_retries + 1
    last_detail = ""

    for attempt in range(attempts):
        started_at = time.perf_counter()
        try:
            response = requests.get(url, params=params, timeout=timeout)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            status_code = getattr(response, "status_code", None)

            if is_retryable_http_status(status_code):
                last_detail = f"HTTP {status_code}"
                logger.warning(
                    "tool=%s status=retryable_http_error attempt=%s/%s http_status=%s elapsed_ms=%s params=%s",
                    tool_name,
                    attempt + 1,
                    attempts,
                    status_code,
                    elapsed_ms,
                    safe_log_params or {},
                )
                if attempt < max_retries:
                    time.sleep(DEFAULT_BACKOFF_SECONDS[min(attempt, len(DEFAULT_BACKOFF_SECONDS) - 1)])
                    continue
                return fail("http_temporary_error", last_detail, retryable=True)

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                logger.error(
                    "tool=%s status=http_failed http_status=%s elapsed_ms=%s params=%s",
                    tool_name,
                    status_code,
                    elapsed_ms,
                    safe_log_params or {},
                )
                return fail("http_request_failed", f"HTTP {status_code}: {exc}", retryable=False)

            try:
                data = response.json()
            except ValueError as exc:
                logger.error(
                    "tool=%s status=invalid_json elapsed_ms=%s params=%s",
                    tool_name,
                    elapsed_ms,
                    safe_log_params or {},
                )
                return fail("invalid_json_response", str(exc), retryable=False)

            logger.info(
                "tool=%s status=success elapsed_ms=%s params=%s",
                tool_name,
                elapsed_ms,
                safe_log_params or {},
            )
            return ok(data)

        except requests.exceptions.Timeout as exc:
            last_detail = str(exc) or "request timed out"
            error_code = "http_request_timeout"
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
            last_detail = str(exc) or exc.__class__.__name__
            error_code = "http_connection_error"

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "tool=%s status=%s attempt=%s/%s elapsed_ms=%s params=%s",
            tool_name,
            error_code,
            attempt + 1,
            attempts,
            elapsed_ms,
            safe_log_params or {},
        )
        if attempt < max_retries:
            time.sleep(DEFAULT_BACKOFF_SECONDS[min(attempt, len(DEFAULT_BACKOFF_SECONDS) - 1)])
            continue
        return fail(error_code, last_detail, retryable=True)

    return fail("http_request_failed", last_detail or "request failed", retryable=True)

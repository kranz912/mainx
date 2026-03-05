from __future__ import annotations

from typing import Any

from .specs import AuthSpec, LoggingSpec, ResponseValidationSpec, RetrySpec


def parse_retries(raw: Any) -> RetrySpec | None:
    if raw is None:
        return None

    data = raw or {}
    return RetrySpec(
        total=int(data.get("total", 0)),
        backoff_factor=float(data.get("backoff_factor", 0.0)),
        status_forcelist=[
            int(v) for v in data.get("status_forcelist", [429, 500, 502, 503, 504])
        ],
        allowed_methods=[
            str(v).upper()
            for v in data.get(
                "allowed_methods",
                ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
            )
        ],
    )


def parse_auth(raw: Any) -> AuthSpec | None:
    if raw is None:
        return None

    data = raw or {}
    return AuthSpec(
        type=str(data.get("type", "none")),
        token=data.get("token"),
        username=data.get("username"),
        password=data.get("password"),
        key=data.get("key"),
        value=data.get("value"),
        in_=str(data.get("in", "header")),
    )


def parse_validation(raw: Any) -> ResponseValidationSpec | None:
    if raw is None:
        return None

    data = raw or {}
    return ResponseValidationSpec(
        raise_for_status=bool(data.get("raise_for_status", True)),
        allowed_statuses=[int(v) for v in data.get("allowed_statuses", [])],
        content_type_contains=data.get("content_type_contains"),
        required_json_fields=[str(v) for v in data.get("required_json_fields", [])],
    )


def parse_logging(raw: Any) -> LoggingSpec | None:
    if raw is None:
        return None

    data = raw or {}
    return LoggingSpec(
        provider=str(data.get("provider", "none")),
        level=str(data.get("level", "INFO")),
        format=str(data.get("format", "%(asctime)s %(levelname)s %(name)s %(message)s")),
        file_path=data.get("file_path") or data.get("location"),
        cloudwatch_log_group=data.get("cloudwatch_log_group") or data.get("log_group"),
        cloudwatch_log_stream=data.get("cloudwatch_log_stream") or data.get("log_stream"),
        cloudwatch_region=data.get("cloudwatch_region") or data.get("region"),
    )

from __future__ import annotations

import logging
from pathlib import Path

from .specs import LoggingSpec


class CloudWatchLogHandler(logging.Handler):
    """Minimal CloudWatch Logs handler using boto3 if available."""

    def __init__(self, spec: LoggingSpec) -> None:
        super().__init__()
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "CloudWatch logging requires boto3 to be installed"
            ) from exc

        if not spec.cloudwatch_log_group or not spec.cloudwatch_log_stream:
            raise ValueError(
                "CloudWatch logging requires cloudwatch_log_group and cloudwatch_log_stream"
            )

        self._client = boto3.client("logs", region_name=spec.cloudwatch_region)
        self._group = spec.cloudwatch_log_group
        self._stream = spec.cloudwatch_log_stream
        self._sequence_token: str | None = None

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        event = {
            "timestamp": int(record.created * 1000),
            "message": message,
        }

        kwargs = {
            "logGroupName": self._group,
            "logStreamName": self._stream,
            "logEvents": [event],
        }
        if self._sequence_token:
            kwargs["sequenceToken"] = self._sequence_token

        response = self._client.put_log_events(**kwargs)
        self._sequence_token = response.get("nextSequenceToken")


def build_logger(client_name: str, spec: LoggingSpec | None) -> logging.Logger | None:
    if spec is None or spec.provider.lower() in {"", "none"}:
        return None

    logger_name = f"maix.{client_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, spec.level.upper(), logging.INFO))
    logger.propagate = False

    # Avoid duplicate handlers across reloads.
    logger.handlers.clear()

    formatter = logging.Formatter(spec.format)
    provider = spec.provider.lower()

    if provider in {"console", "stdout", "stream"}:
        handler: logging.Handler = logging.StreamHandler()
    elif provider in {"file", "raw_file"}:
        if not spec.file_path:
            raise ValueError("File logging requires 'file_path'")
        Path(spec.file_path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(spec.file_path, encoding="utf-8")
    elif provider == "cloudwatch":
        handler = CloudWatchLogHandler(spec)
    else:
        raise ValueError(f"Unsupported logging provider: {spec.provider}")

    handler.setLevel(getattr(logging, spec.level.upper(), logging.INFO))
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

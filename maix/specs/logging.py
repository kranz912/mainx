from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoggingSpec:
    provider: str = "none"
    level: str = "INFO"
    format: str = "%(asctime)s %(levelname)s %(name)s %(message)s"
    file_path: str | None = None
    cloudwatch_log_group: str | None = None
    cloudwatch_log_stream: str | None = None
    cloudwatch_region: str | None = None

from __future__ import annotations

from dataclasses import dataclass, field

from .auth import AuthSpec
from .logging import LoggingSpec
from .retry import RetrySpec
from .validation import ResponseValidationSpec


@dataclass
class EndpointSpec:
    method: str
    path: str
    timeout: float | None = None
    headers: dict[str, str] = field(default_factory=dict)
    retries: RetrySpec | None = None
    auth: AuthSpec | None = None
    validation: ResponseValidationSpec | None = None
    logging: LoggingSpec | None = None

"""Backward-compatible import surface for client and spec classes."""

from .http_client import ConfigHttpClient
from .specs import (
    AuthSpec,
    EndpointSpec,
    LoggingSpec,
    ResponseValidationSpec,
    RetrySpec,
)

__all__ = [
    "AuthSpec",
    "ConfigHttpClient",
    "EndpointSpec",
    "LoggingSpec",
    "ResponseValidationSpec",
    "RetrySpec",
]

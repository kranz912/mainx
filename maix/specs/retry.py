from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrySpec:
    total: int = 0
    backoff_factor: float = 0.0
    status_forcelist: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    allowed_methods: list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    )

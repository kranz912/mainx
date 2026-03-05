from __future__ import annotations

from dataclasses import dataclass, field

import requests


@dataclass
class ResponseValidationSpec:
    raise_for_status: bool = True
    allowed_statuses: list[int] = field(default_factory=list)
    content_type_contains: str | None = None
    required_json_fields: list[str] = field(default_factory=list)

    def validate(self, response: requests.Response) -> None:
        if self.raise_for_status:
            response.raise_for_status()

        if self.allowed_statuses and response.status_code not in self.allowed_statuses:
            raise ValueError(
                f"Unexpected status code {response.status_code}. "
                f"Allowed: {self.allowed_statuses}"
            )

        if self.content_type_contains:
            content_type = response.headers.get("Content-Type", "")
            if self.content_type_contains.lower() not in content_type.lower():
                raise ValueError(
                    f"Unexpected content type '{content_type}'. "
                    f"Expected to include '{self.content_type_contains}'."
                )

        if self.required_json_fields:
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("Response is not valid JSON") from exc

            if not isinstance(payload, dict):
                raise ValueError("JSON response must be an object for required field checks")

            missing = [field for field in self.required_json_fields if field not in payload]
            if missing:
                raise ValueError(f"Missing required JSON fields: {missing}")

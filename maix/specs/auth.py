from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuthSpec:
    type: str = "none"
    token: str | None = None
    username: str | None = None
    password: str | None = None
    key: str | None = None
    value: str | None = None
    in_: str = "header"

    def apply(
        self,
        headers: dict[str, str],
        params: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, Any], tuple[str, str] | None]:
        kind = self.type.lower()
        auth: tuple[str, str] | None = None

        if kind in {"none", ""}:
            return headers, params, auth

        if kind == "bearer":
            if not self.token:
                raise ValueError("Auth type 'bearer' requires 'token'")
            headers["Authorization"] = f"Bearer {self.token}"
            return headers, params, auth

        if kind == "basic":
            if self.username is None or self.password is None:
                raise ValueError("Auth type 'basic' requires 'username' and 'password'")
            auth = (self.username, self.password)
            return headers, params, auth

        if kind == "api_key":
            if not self.key or self.value is None:
                raise ValueError("Auth type 'api_key' requires 'key' and 'value'")
            if self.in_.lower() == "query":
                params[self.key] = self.value
            else:
                headers[self.key] = self.value
            return headers, params, auth

        raise ValueError(f"Unsupported auth type: {self.type}")

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config_parser import parse_auth, parse_logging, parse_retries, parse_validation
from .http_client import ConfigHttpClient
from .specs import EndpointSpec


class ConfigHttpLibrary:
    """Loads all YAML configs from a folder and exposes named clients."""

    def __init__(self, config_dir: str | Path = "config") -> None:
        self.config_dir = Path(config_dir)
        self.clients: dict[str, ConfigHttpClient] = {}
        self.reload()

    def reload(self) -> None:
        self.clients.clear()

        if not self.config_dir.exists():
            return

        config_files = sorted(
            [
                *self.config_dir.glob("*.yml"),
                *self.config_dir.glob("*.yaml"),
            ]
        )

        for file_path in config_files:
            client_name = file_path.stem.lower()
            self.clients[client_name] = self._load_client(file_path, client_name)

    def _load_client(self, file_path: Path, client_name: str) -> ConfigHttpClient:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}

        base_url = raw.get("base_url")
        if not base_url:
            raise ValueError(f"Missing 'base_url' in config: {file_path}")

        default_timeout = float(raw.get("timeout", 10.0))
        default_headers = raw.get("headers", {}) or {}
        default_retries = parse_retries(raw.get("retries"))
        default_auth = parse_auth(raw.get("auth"))
        default_validation = parse_validation(raw.get("validation"))
        default_logging = parse_logging(raw.get("logging"))

        endpoints_section = raw.get("endpoints", {}) or {}
        endpoints: dict[str, EndpointSpec] = {}

        for endpoint_name, endpoint_raw in endpoints_section.items():
            endpoint_data = endpoint_raw or {}
            method = str(endpoint_data.get("method", "GET")).upper()
            path = endpoint_data.get("path")
            if not path:
                raise ValueError(
                    f"Missing 'path' for endpoint '{endpoint_name}' in {file_path}"
                )

            endpoint_timeout = endpoint_data.get("timeout")
            endpoints[endpoint_name] = EndpointSpec(
                method=method,
                path=path,
                timeout=float(endpoint_timeout) if endpoint_timeout is not None else None,
                headers=endpoint_data.get("headers", {}) or {},
                retries=parse_retries(endpoint_data.get("retries")),
                auth=parse_auth(endpoint_data.get("auth")),
                validation=parse_validation(endpoint_data.get("validation")),
                logging=parse_logging(endpoint_data.get("logging")),
            )

        return ConfigHttpClient(
            name=client_name,
            base_url=base_url,
            default_timeout=default_timeout,
            default_headers=default_headers,
            default_retries=default_retries,
            default_auth=default_auth,
            default_validation=default_validation,
            default_logging=default_logging,
            endpoints=endpoints,
        )

    def get(self, name: str) -> ConfigHttpClient:
        key = name.lower()
        if key not in self.clients:
            raise KeyError(f"No configured client named '{name}'")
        return self.clients[key]

    def __getitem__(self, name: str) -> ConfigHttpClient:
        return self.get(name)

    def __getattr__(self, name: str) -> ConfigHttpClient:
        # Supports: api.weather.call(...)
        try:
            return self.get(name)
        except KeyError as exc:
            raise AttributeError(name) from exc

    def list_clients(self) -> list[str]:
        return sorted(self.clients.keys())

    def raw_config(self) -> dict[str, Any]:
        return {name: client.base_url for name, client in self.clients.items()}

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .config_parser import parse_auth, parse_logging, parse_retries, parse_validation
from .http_client import ConfigHttpClient
from .schema import ClientConfigModel, model_to_dict
from .secrets import SecretResolver, interpolate_config_values
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

        # First pass resolves env placeholders so provider configs can be read.
        env_resolved = interpolate_config_values(raw, SecretResolver.env_only())
        if not isinstance(env_resolved, dict):
            raise ValueError(f"Config root must be an object: {file_path}")

        resolver = SecretResolver.from_config_dict(env_resolved.get("secrets"))
        resolved = interpolate_config_values(env_resolved, resolver)
        if not isinstance(resolved, dict):
            raise ValueError(f"Config root must be an object: {file_path}")

        try:
            config = ClientConfigModel.model_validate(resolved)
        except ValidationError as exc:
            raise ValueError(f"Invalid config {file_path}: {exc}") from exc

        default_timeout = config.timeout
        default_headers = config.headers or {}
        default_retries = parse_retries(model_to_dict(config.retries))
        default_auth = parse_auth(model_to_dict(config.auth))
        default_validation = parse_validation(model_to_dict(config.validation))
        default_logging = parse_logging(model_to_dict(config.logging))

        endpoints_section = config.endpoints or {}
        endpoints: dict[str, EndpointSpec] = {}

        for endpoint_name, endpoint_cfg in endpoints_section.items():
            method = endpoint_cfg.method.upper()
            path = endpoint_cfg.path
            endpoint_timeout = endpoint_cfg.timeout
            endpoints[endpoint_name] = EndpointSpec(
                method=method,
                path=path,
                timeout=float(endpoint_timeout) if endpoint_timeout is not None else None,
                headers=endpoint_cfg.headers or {},
                retries=parse_retries(model_to_dict(endpoint_cfg.retries)),
                auth=parse_auth(model_to_dict(endpoint_cfg.auth)),
                validation=parse_validation(model_to_dict(endpoint_cfg.validation)),
                logging=parse_logging(model_to_dict(endpoint_cfg.logging)),
                response_model=endpoint_cfg.response_model,
            )

        return ConfigHttpClient(
            name=client_name,
            base_url=config.base_url,
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

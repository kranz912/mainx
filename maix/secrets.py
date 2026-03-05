from __future__ import annotations

import os
import re
from typing import Protocol

import requests

from .schema import SecretsConfigModel


TOKEN_PATTERN = re.compile(r"\$\{([^}]+)\}")


class SecretProvider(Protocol):
    def get(self, key: str) -> str:
        ...


class EnvSecretProvider:
    def get(self, key: str) -> str:
        value = os.getenv(key)
        if value is None:
            raise KeyError(f"Environment variable not found: {key}")
        return value


class AwsSsmSecretProvider:
    def __init__(self, region: str | None = None, with_decryption: bool = True) -> None:
        self._region = region
        self._with_decryption = with_decryption

    def get(self, key: str) -> str:
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "AWS SSM provider requires boto3. Install with: pip install -e .[secrets]"
            ) from exc

        client = boto3.client("ssm", region_name=self._region)
        response = client.get_parameter(Name=key, WithDecryption=self._with_decryption)
        value = response["Parameter"]["Value"]
        return str(value)


class VaultSecretProvider:
    def __init__(self, url: str, token: str | None, token_env: str | None, timeout: float = 5.0) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._token_env = token_env
        self._timeout = timeout

    def get(self, key: str) -> str:
        token = self._token
        if token is None and self._token_env:
            token = os.getenv(self._token_env)

        if not token:
            raise ValueError("Vault token is missing. Provide token or token_env.")

        path, field = self._split_key(key)
        headers = {"X-Vault-Token": token}
        response = requests.get(f"{self._url}/v1/{path.lstrip('/')}", headers=headers, timeout=self._timeout)
        response.raise_for_status()

        payload = response.json() or {}
        data = payload.get("data", {})

        # KV v2 wraps secrets in data.data
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            data = data["data"]

        if field is None:
            if isinstance(data, str):
                return data
            raise ValueError("Vault key without field must resolve to a string value")

        if not isinstance(data, dict) or field not in data:
            raise KeyError(f"Vault field not found: {key}")

        return str(data[field])

    @staticmethod
    def _split_key(key: str) -> tuple[str, str | None]:
        if "#" in key:
            path, field = key.split("#", 1)
            return path, field
        return key, None


class SecretResolver:
    def __init__(self) -> None:
        self._providers: dict[str, SecretProvider] = {
            "ENV": EnvSecretProvider(),
        }

    @classmethod
    def env_only(cls) -> "SecretResolver":
        return cls()

    @classmethod
    def from_config_dict(cls, secrets_raw: dict | None) -> "SecretResolver":
        resolver = cls()
        if not secrets_raw:
            return resolver

        config = SecretsConfigModel.model_validate(secrets_raw)
        if config.ssm is not None:
            resolver._providers["SSM"] = AwsSsmSecretProvider(
                region=config.ssm.region,
                with_decryption=config.ssm.with_decryption,
            )
        if config.vault is not None:
            resolver._providers["VAULT"] = VaultSecretProvider(
                url=config.vault.url,
                token=config.vault.token,
                token_env=config.vault.token_env,
                timeout=config.vault.timeout,
            )
        return resolver

    def interpolate(self, value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            token = match.group(1)
            return self.resolve_token(token)

        return TOKEN_PATTERN.sub(replace, value)

    def resolve_token(self, token: str) -> str:
        if ":" in token:
            prefix, key = token.split(":", 1)
            provider_name = prefix.upper()
            provider = self._providers.get(provider_name)
            if provider is None:
                raise KeyError(f"Unknown secret provider: {prefix}")
            return provider.get(key)

        # Default style ${API_KEY} resolves from environment.
        return self._providers["ENV"].get(token)


def interpolate_config_values(value: object, resolver: SecretResolver) -> object:
    if isinstance(value, dict):
        return {k: interpolate_config_values(v, resolver) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate_config_values(v, resolver) for v in value]
    if isinstance(value, str):
        return resolver.interpolate(value)
    return value
